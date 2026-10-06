# Per-chat project folders (experimental)

Open WebUI Desktop can link a local folder to each saved chat. The link is stored only in the desktop app, and its working directory is restored whenever that chat is opened again.

## Windows workflow

1. Connect Desktop to your Open WebUI server and sign in.
2. Open a saved chat (`/c/<chat-id>`).
3. Click **Choose project** in the Desktop status bar.
4. Pick a folder in the native Windows folder picker.

Desktop will start or install Open Terminal when needed, configure the chat's session working directory, and add the localhost Open Terminal as a personal Direct Terminal connection for the signed-in Open WebUI account. If the personal connection is added for the first time, the embedded page reloads once so Open WebUI can use it immediately.

Use the adjacent actions to open the folder in File Explorer or unlink it from the chat. Unlinking does not delete any files.

## Requirements

- Open Terminal 0.11.32 or newer for per-session working directories.
- The remote Open WebUI server must allow personal direct integrations for the signed-in account.
- The Windows PC must be able to download Python and Open Terminal during first-time setup.

## Security boundary

The selected project folder is a working directory, not a sandbox. Open Terminal runs with the same filesystem permissions as the Windows user and shell commands can still access absolute paths outside the selected folder. Use a Windows account with appropriate permissions and review file changes before keeping them.

The local Open Terminal listens on `127.0.0.1` and uses a generated API key. For a remote Open WebUI server, it is registered as a personal/direct connection so `127.0.0.1` correctly refers to the user's PC rather than the remote server.
