-- Keep the core local-assistant capabilities while avoiding a large set of
-- unrelated built-in tool schemas on every native function-calling request.
-- Explicitly selected external Tools, Skills, Terminal and Fireworks remain
-- available; this only trims the default built-in catalogue.
BEGIN IMMEDIATE;

UPDATE model
SET meta = json_set(
  COALESCE(meta, '{}'),
  '$.builtinTools.time', 1,
  '$.builtinTools.user_input', 1,
  '$.builtinTools.knowledge', 1,
  '$.builtinTools.web_search', 1,
  '$.builtinTools.image_generation', 1,
  '$.builtinTools.code_interpreter', 1,
  '$.builtinTools.chats', 0,
  '$.builtinTools.subagents', 0,
  '$.builtinTools.memory', 0,
  '$.builtinTools.notes', 0,
  '$.builtinTools.channels', 0,
  '$.builtinTools.tasks', 0,
  '$.builtinTools.automations', 0,
  '$.builtinTools.calendar', 0,
  '$.builtinTools.notifications', 0
),
updated_at = CAST(strftime('%s', 'now') AS INTEGER)
WHERE json_extract(params, '$.function_calling') = 'native';

COMMIT;
