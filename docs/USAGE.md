# Usage Guide

This document explains how to use the Role Assignment Bot once it is invited to your server.

Quick start
- The first person to successfully run a command becomes the admin for that server.
- Admin configures a moderator role or individual moderators, and sets allowed roles.
- When a new member joins, a control panel is posted in the assignment channel for quick role toggling.

Slash command reference

Setup (admin only)
- /setup set_moderator_role role:<Role>
  - Anyone with this Discord role is treated as a moderator by the bot.
- /setup set_assignment_channel [channel:<TextChannel>]
  - Choose an existing text channel, or omit to have the bot create a private one for staff.

Admin
- /admin add_moderator user:<User>
  - Grants moderator permissions to a specific user.
- /admin remove_moderator user:<User>
  - Revokes moderator permissions from a user.
- /admin list_moderators
  - Shows the current list of moderator users.
- /admin resync
  - Forces a re-sync of slash commands. Useful after first install or permission changes.

Allowed roles (admin only)
- /roles_allow add role:<Role>
  - Adds a role to the whitelist that moderators can assign/remove.
- /roles_allow remove role:<Role>
  - Removes a role from the whitelist.
- /roles_allow list
  - Shows the currently allowed roles (visible to moderators and admin).

Moderator actions
- /assign member:<Member> role:<Allowed Role>
  - Assigns an allowed role to a member.
- /remove member:<Member> role:<Allowed Role>
  - Removes an allowed role from a member.
- /simulate_rejoin member:<Member>
  - Simulates that the specified member just joined. Posts the same control panel in the assignment channel so you can test role toggles without the user actually leaving and rejoining. Only available to moderators/admin.
- Control panel buttons
  - On member join, a pinned message with buttons lets you toggle roles on that specific member.

Ephemeral vs public responses
- Most command responses are ephemeral (visible only to the user who ran the command) especially when they involve permissions or member info.
- The control panel message is posted in a staff-only channel; button click acknowledgements are ephemeral.

Auto-delete / immovable messages
- Discord does not provide truly "undeletable" messages. The bot pins the control panel to reduce accidental deletion.
- Staff with Manage Messages permission can still delete it; it will be recreated for the next new join.

Admin workflows
1) First-time setup
   - Run any setup/admin command; you become the admin.
   - /setup set_moderator_role or use /admin add_moderator for individuals.
   - Add allowed roles with /roles_allow add.
   - Optionally set a dedicated channel with /setup set_assignment_channel.
2) Day-to-day
   - Use the join panel to toggle roles or run /assign and /remove.
3) Troubleshooting
   - If commands are missing, use /admin resync; ensure the bot has applications.commands scope.

Notes
- The bot requires its role to be above any roles it should manage.
- Managed roles (from integrations) cannot be assigned or removed by bots.
- If ALLOWED_GUILDS is set, the bot only operates in those servers.
