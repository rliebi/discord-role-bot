# Setup the Discord Application and Bot

Follow these steps to create and invite your bot with the minimum required permissions and scopes.

1) Create the application and bot user
- Go to https://discord.com/developers/applications and click "New Application".
- Give it a name (e.g., RoleBot) and create.
- In the left sidebar, open the "Bot" tab and click "Add Bot".
- Copy the Bot Token. You will set it as environment variable DISCORD_TOKEN in your deployment.

2) Enable Privileged Intent
- Still in the "Bot" tab, enable the "SERVER MEMBERS INTENT" (aka Members intent).
- Save changes.

3) Configure OAuth2 scopes and permissions (invite URL)
- Go to the "OAuth2" -> "URL Generator" page.
- In Scopes, check: `bot` and `applications.commands`.
- In Bot Permissions, select the minimal set:
  - Manage Roles
  - View Channels
  - Send Messages
  - Read Message History
  - Manage Messages (optional, for pinning control messages)
  - Use Slash Commands
- Copy the generated URL at the bottom.

4) Invite the bot to your server
- Open the invite URL in your browser and select your target server (you need the Manage Server permission).
- Confirm the permissions and authorize.

5) Place the bot role correctly
- In your server, drag the bot's highest role above any roles it must assign/remove.
- Otherwise Discord will forbid the bot from managing those roles.

6) Optional: Restrict where the bot works
- If you want to limit the bot to specific servers, set the `ALLOWED_GUILDS` environment variable with a comma-separated list of guild IDs (e.g., `1234,5678`).

7) Get your Guild ID(s)
- In Discord client, enable Developer Mode (User Settings -> Advanced -> Developer Mode).
- Right-click your server icon and choose "Copy Server ID".
