def validate_story_id(story_id: int) -> None:
    if type(story_id) is not int or story_id < 1:
        raise ValueError("story_id must be a positive integer")
