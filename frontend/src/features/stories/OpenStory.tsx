import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowRight } from "lucide-react";

export function OpenStory({ hero = false }: { hero?: boolean }) {
  const [id, setId] = useState("");
  const navigate = useNavigate();
  return (
    <form
      className={`open-story ${hero ? "hero-search" : ""}`}
      onSubmit={(e) => {
        e.preventDefault();
        if (/^[1-9]\d*$/.test(id)) navigate(`/stories/${id}`);
      }}
    >
      <label
        htmlFor={hero ? "hero-id" : "story-id"}
        className={hero ? "" : "sr-only"}
      >
        {hero ? "MÁTE ČÍSLO USER STORY?" : "ID User Story"}
      </label>
      <div>
        <span className="input-prefix">#</span>
        <input
          id={hero ? "hero-id" : "story-id"}
          type="text"
          inputMode="numeric"
          pattern="[1-9][0-9]*"
          value={id}
          onChange={(e) => setId(e.target.value)}
          placeholder="Zadajte ID User Story"
          required
          aria-label="ID User Story"
        />
        <button className="button button-primary" type="submit">
          Otvoriť <ArrowRight size={17} />
        </button>
      </div>
    </form>
  );
}
