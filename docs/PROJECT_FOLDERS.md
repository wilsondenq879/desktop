# Per-chat project folders (experimental)

Open WebUI Desktop can link a local folder to each saved chat. The link is stored only in the desktop app, and its working directory is restored whenever that chat is opened again.

## Windows workflow

1. Connect Desktop to your Open WebUI server and sign in.
2. Optionally click **Choose project** in the Desktop status bar before starting a new chat.
3. Pick a folder in the native Windows folder picker, or start immediately in a temporary workspace.
4. Start the new chat. Desktop prepares the folder and local file tools before the first request is sent.

The selected folder is a one-shot choice for the next new chat only. It is cleared after that chat claims it, so a later new chat can never inherit the preceding chat's folder. Existing chats keep their own saved mapping and never fall back to a pending new-chat selection. Desktop starts Open Terminal with the selected folder as its root working directory, configures each saved chat's session directory, and attaches the localhost file tools to each chat request. The embedded page reloads after folder selection so Open WebUI can refresh its local tools.

If no folder is selected, Desktop creates a unique temporary workspace under its application data directory. The model can create files there immediately without asking where to save them. When the user later chooses a permanent project folder for that chat, Desktop recursively moves the temporary files into it. Existing destination files are never overwritten: conflicting files receive an `Open WebUI tmp` suffix, and unsupported entries remain in the temporary workspace for review.

When a request produces a file, Desktop identifies the selected project folder as the default destination. The model is instructed to create and verify the artifact there without asking the user to repeat the location, and it must not fall back to a generic "the browser cannot access your filesystem" response while the Desktop tools are available.

Use the adjacent actions to open the folder in File Explorer or unlink it from the chat. Unlinking does not delete any files; the chat switches to a fresh isolated temporary workspace.

## Requirements

- Open Terminal 0.11.32 or newer for per-session working directories.
- The remote Open WebUI server must allow personal direct integrations for the signed-in account.
- The Windows PC must be able to download Python and Open Terminal during first-time setup.

## Security boundary

The selected project folder is a working directory, not a sandbox. Open Terminal runs with the same filesystem permissions as the Windows user and shell commands can still access absolute paths outside the selected folder. Use a Windows account with appropriate permissions and review file changes before keeping them.

The local Open Terminal listens on `127.0.0.1` and uses a generated API key. For a remote Open WebUI server, it is registered as a personal/direct connection so `127.0.0.1` correctly refers to the user's PC rather than the remote server.
