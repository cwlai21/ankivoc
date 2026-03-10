LangChain AI helpers and experiments
===================================

A small workspace for generating Anki vocabulary notes using LLMs and Azure TTS.

## Notes about backend placeholders

- The `backend/` Django app folders contain starter files for `accounts`, `languages`, and `cards`.
- Several modules currently include placeholder comments instead of implemented models/views/tests. This is intentional to avoid unused-import noise during static analysis.
- When implementing features, add model/admin/view/test code into the respective files under `backend/<app>/`.

If you want, I can remove the placeholder comments and scaffold basic examples for each app.

