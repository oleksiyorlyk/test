
const USERS_KEY="yourtask.users";
const SESSION_KEY="yourtask.session";
const TASKS_KEY_PREFIX="yourtask.tasks.";

const $=id=>document.getElementById(id);
let currentUser=null;
let tasks=[];
let activeStatus="all";

const authPage=$("authPage"), workspacePage=$("workspacePage");
const registerTab=$("registerTab"), loginTab=$("loginTab");
const registerView=$("registerView"), loginView=$("loginView");
const registerForm=$("registerForm"), loginForm=$("loginForm");

registerTab.onclick=()=>showAuth("register");
loginTab.onclick=()=>showAuth("login");

$("registerPassword").addEventListener("input",updatePasswordRules);

registerForm.addEventListener("submit",e=>{
  e.preventDefault(); clearRegisterErrors();
  const name=$("registerName").value.trim();
  const email=normalizeEmail($("registerEmail").value);
  const password=$("registerPassword").value;
  const confirmation=$("confirmPassword").value;
  let invalid=false;

  if(!name){$("registerNameError").textContent="Name is required.";invalid=true}
  else if(name.length<2){$("registerNameError").textContent="Name must contain at least 2 characters.";invalid=true}

  if(!email){$("registerEmailError").textContent="Email is required.";invalid=true}
  else if(!validEmail(email)){$("registerEmailError").textContent="Enter a valid email address.";invalid=true}

  if(!password){$("registerPasswordError").textContent="Password is required.";invalid=true}
  else if(!strongPassword(password)){$("registerPasswordError").textContent="Password does not meet all required rules.";invalid=true}

  if(!confirmation){$("confirmPasswordError").textContent="Please confirm your password.";invalid=true}
  else if(confirmation!==password){$("confirmPasswordError").textContent="Passwords do not match.";invalid=true}

  if(!$("termsCheckbox").checked){$("termsError").textContent="You must accept the Terms of Use and Privacy Policy.";invalid=true}
  if(invalid)return;

  const users=getUsers();
  if(users.some(u=>u.email===email)){
    $("registerGlobalError").textContent="An account with this email already exists.";
    return;
  }

  const user={id:crypto.randomUUID(),name,email,password};
  users.push(user);
  localStorage.setItem(USERS_KEY,JSON.stringify(users));
  sessionStorage.setItem(SESSION_KEY,email);
  enterWorkspace(user);
  toast("Account created");
});

loginForm.addEventListener("submit",e=>{
  e.preventDefault(); clearLoginErrors();
  const email=normalizeEmail($("loginEmail").value);
  const password=$("loginPassword").value;
  let invalid=false;

  if(!email){$("loginEmailError").textContent="Email is required.";invalid=true}
  else if(!validEmail(email)){$("loginEmailError").textContent="Enter a valid email address.";invalid=true}
  if(!password){$("loginPasswordError").textContent="Password is required.";invalid=true}
  if(invalid)return;

  const user=getUsers().find(u=>u.email===email && u.password===password);
  if(!user){$("loginGlobalError").textContent="Incorrect email or password.";return}
  sessionStorage.setItem(SESSION_KEY,email);
  enterWorkspace(user);
  toast("Signed in");
});

$("logoutButton").onclick=()=>{
  sessionStorage.removeItem(SESSION_KEY);
  currentUser=null; tasks=[];
  showAuth("login");
  toast("Signed out");
};

document.querySelectorAll("[data-status-filter]").forEach(btn=>{
  btn.addEventListener("click",()=>{
    activeStatus=btn.dataset.statusFilter;
    document.querySelectorAll("[data-status-filter]").forEach(x=>x.classList.remove("active"));
    btn.classList.add("active");
    renderTasks();
  });
});

$("searchInput").addEventListener("input",renderTasks);
$("priorityFilter").addEventListener("change",renderTasks);
$("sortSelect").addEventListener("change",renderTasks);

$("newTaskButton").onclick=()=>openTaskModal();
$("closeTaskModal").onclick=closeTaskModal;
$("cancelTaskButton").onclick=closeTaskModal;
$("taskModal").addEventListener("click",e=>{if(e.target===$("taskModal"))closeTaskModal()});

$("taskForm").addEventListener("submit",e=>{
  e.preventDefault();
  $("taskTitleError").textContent="";
  const title=$("taskTitle").value.trim();

  if(!title){
    $("taskTitleError").textContent="Task title is required.";
    return;
  }

  const id=$("editingTaskId").value;
  if(id){
    const task=tasks.find(t=>t.id===id);
    if(task){
      task.title=title;
      task.description=$("taskDescription").value.trim();
      task.priority=$("taskPriority").value;
      task.status=$("taskStatus").value;
      task.dueDate=$("taskDueDate").value;
    }
    toast("Task updated");
  }else{
    tasks.unshift({
      id:crypto.randomUUID(),
      title,
      description:$("taskDescription").value.trim(),
      priority:$("taskPriority").value,
      status:$("taskStatus").value,
      dueDate:$("taskDueDate").value,
      createdAt:Date.now()
    });
    toast("Task created");
  }

  saveTasks(); closeTaskModal(); renderTasks();
});

function enterWorkspace(user){
  currentUser=user;
  authPage.classList.add("hidden");
  workspacePage.classList.remove("hidden");
  $("sidebarUserName").textContent=user.name;
  $("sidebarUserEmail").textContent=user.email;
  $("userInitials").textContent=user.name.split(/\s+/).map(x=>x[0]).join("").slice(0,2).toUpperCase();
  $("greetingTitle").textContent=`Hello, ${user.name.split(" ")[0]}`;
  tasks=loadTasks(user.email);
  renderTasks();
}

function showAuth(mode){
  workspacePage.classList.add("hidden");
  authPage.classList.remove("hidden");
  const reg=mode==="register";
  registerView.classList.toggle("hidden",!reg);
  loginView.classList.toggle("hidden",reg);
  registerTab.classList.toggle("active",reg);
  loginTab.classList.toggle("active",!reg);
  clearRegisterErrors(); clearLoginErrors();
}

function openTaskModal(task=null){
  $("taskForm").reset();
  $("taskTitleError").textContent="";
  $("editingTaskId").value="";
  $("taskPriority").value="medium";
  $("taskStatus").value="todo";

  if(task){
    $("taskModalTitle").textContent="Edit task";
    $("editingTaskId").value=task.id;
    $("taskTitle").value=task.title;
    $("taskDescription").value=task.description||"";
    $("taskPriority").value=task.priority;
    $("taskStatus").value=task.status;
    $("taskDueDate").value=task.dueDate||"";
  }else{
    $("taskModalTitle").textContent="Create task";
  }

  $("taskModal").classList.remove("hidden");
}

function closeTaskModal(){$("taskModal").classList.add("hidden")}

function renderTasks(){
  if(!currentUser)return;
  const query=$("searchInput").value.trim().toLowerCase();
  const priority=$("priorityFilter").value;

  let list=tasks.filter(t=>{
    const statusOk=activeStatus==="all"||t.status===activeStatus;
    const priorityOk=priority==="all"||t.priority===priority;
    const queryOk=!query||t.title.toLowerCase().includes(query)||(t.description||"").toLowerCase().includes(query);
    return statusOk&&priorityOk&&queryOk;
  });

  if($("sortSelect").value==="priority"){
    const order={high:0,medium:1,low:2};
    list.sort((a,b)=>order[a.priority]-order[b.priority]);
  }else if($("sortSelect").value==="dueDate"){
    list.sort((a,b)=>(a.dueDate||"9999-12-31").localeCompare(b.dueDate||"9999-12-31"));
  }else if($("sortSelect").value==="title"){
    list.sort((a,b)=>a.title.localeCompare(b.title));
  }else{
    list.sort((a,b)=>b.createdAt-a.createdAt);
  }

  $("taskList").innerHTML="";
  list.forEach(task=>$("taskList").appendChild(taskRow(task)));
  $("emptyState").classList.toggle("hidden",list.length>0);
  $("visibleTaskCount").textContent=`${list.length} ${list.length===1?"task":"tasks"}`;

  const labels={
    all:["All tasks","Everything in one place."],
    todo:["To do","Tasks waiting to be started."],
    inprogress:["In progress","Tasks currently being worked on."],
    done:["Completed","Finished tasks."]
  };
  $("taskSectionTitle").textContent=labels[activeStatus][0];
  $("taskSectionSubtitle").textContent=labels[activeStatus][1];
  updateStats();
}

function taskRow(task){
  const row=document.createElement("article");
  row.className=`task-row ${task.status==="done"?"done":""}`;
  row.dataset.testid=`task-row-${task.id}`;

  const statusLabel={todo:"To do",inprogress:"In progress",done:"Completed"}[task.status];
  const statusClass=task.status==="done"?"done-badge":task.status;

  row.innerHTML=`
    <div class="task-main">
      <button class="check-btn ${task.status==="done"?"checked":""}" data-action="toggle" data-testid="task-toggle-${task.id}">${task.status==="done"?"✓":""}</button>
      <div class="task-copy">
        <h3 data-testid="task-title-${task.id}">${escapeHtml(task.title)}</h3>
        <p>${escapeHtml(task.description||"No description")}</p>
      </div>
    </div>
    <span class="badge ${statusClass}">${statusLabel}</span>
    <span class="badge ${task.priority}">${capitalize(task.priority)}</span>
    <span class="date-cell">${task.dueDate?formatDate(task.dueDate):"No due date"}</span>
    <div class="row-actions">
      <button data-action="edit" data-testid="task-edit-${task.id}" aria-label="Edit">✎</button>
      <button data-action="delete" data-testid="task-delete-${task.id}" aria-label="Delete">⌫</button>
    </div>`;

  row.querySelector('[data-action="toggle"]').onclick=()=>{
    task.status=task.status==="done"?"todo":"done";
    saveTasks(); renderTasks(); toast(task.status==="done"?"Task completed":"Task reopened");
  };

  row.querySelector('[data-action="edit"]').onclick=()=>openTaskModal(task);

  row.querySelector('[data-action="delete"]').onclick=()=>{
    if(!confirm(`Delete "${task.title}"?`))return;
    tasks=tasks.filter(t=>t.id!==task.id);
    saveTasks(); renderTasks(); toast("Task deleted");
  };

  return row;
}

function updateStats(){
  $("statTotal").textContent=tasks.length;
  $("statTodo").textContent=tasks.filter(t=>t.status==="todo").length;
  $("statProgress").textContent=tasks.filter(t=>t.status==="inprogress").length;
  $("statDone").textContent=tasks.filter(t=>t.status==="done").length;
}

function loadTasks(email){
  try{return JSON.parse(localStorage.getItem(TASKS_KEY_PREFIX+email))||[]}
  catch{return[]}
}

function saveTasks(){
  localStorage.setItem(TASKS_KEY_PREFIX+currentUser.email,JSON.stringify(tasks));
}

function getUsers(){
  try{return JSON.parse(localStorage.getItem(USERS_KEY))||[]}
  catch{return[]}
}

function restore(){
  const email=sessionStorage.getItem(SESSION_KEY);
  if(!email){showAuth("register");return}
  const user=getUsers().find(u=>u.email===email);
  if(!user){sessionStorage.removeItem(SESSION_KEY);showAuth("register");return}
  enterWorkspace(user);
}

function updatePasswordRules(){
  const v=$("registerPassword").value;
  setRule($("ruleLength"),v.length>=6);
  setRule($("ruleNumber"),/\d/.test(v));
  setRule($("ruleSymbol"),/[^A-Za-z0-9]/.test(v));
}
function setRule(el,ok){el.classList.toggle("ok",ok);el.querySelector("span").textContent=ok?"✓":"•"}
function strongPassword(v){return v.length>=6&&/\d/.test(v)&&/[^A-Za-z0-9]/.test(v)}
function validEmail(v){return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v)}
function normalizeEmail(v){return v.trim().toLowerCase()}
function clearRegisterErrors(){["registerNameError","registerEmailError","registerPasswordError","confirmPasswordError","termsError","registerGlobalError"].forEach(id=>$(id).textContent="")}
function clearLoginErrors(){["loginEmailError","loginPasswordError","loginGlobalError"].forEach(id=>$(id).textContent="")}
function capitalize(v){return v[0].toUpperCase()+v.slice(1)}
function formatDate(v){return new Date(v+"T00:00:00").toLocaleDateString(undefined,{day:"2-digit",month:"short",year:"numeric"})}
function escapeHtml(v){return String(v).replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;").replaceAll("'","&#039;")}
function toast(message){const t=$("toast");t.textContent=message;t.classList.remove("hidden");clearTimeout(toast.timer);toast.timer=setTimeout(()=>t.classList.add("hidden"),1500)}

window.YourTaskTest={
  reset(){
    localStorage.clear();
    sessionStorage.clear();
    location.reload();
  },
  seedUser(user={}){
    const seeded={
      id:"test-user-001",
      name:user.name||"Test User",
      email:normalizeEmail(user.email||"test.user@yourtask.local"),
      password:user.password||"Test12!"
    };
    localStorage.setItem(USERS_KEY,JSON.stringify([seeded]));
    sessionStorage.removeItem(SESSION_KEY);
    return seeded;
  },
  seedTasks(email,seed=[]){
    localStorage.setItem(TASKS_KEY_PREFIX+normalizeEmail(email),JSON.stringify(seed));
  }
};

restore();
updatePasswordRules();
