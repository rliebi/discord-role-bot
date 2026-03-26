import asyncio
import logging
import os
import time
import atexit
from typing import Optional, List

import discord
from discord import app_commands, Interaction, Object
from discord.ext import commands

from .config import Settings
from .storage import Storage, GuildConfig

# basic logger; will adjust level after loading settings
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rolebot")


INTENTS = discord.Intents.none()
INTENTS.guilds = True
INTENTS.members = True  # required for member join and role management


class RoleToggleView(discord.ui.View):
    def __init__(self, member: discord.Member, allowed_roles: List[discord.Role], timeout: Optional[float] = None):
        super().__init__(timeout=timeout)
        self.member = member
        # Prefix button labels with checkmarks to reflect current assignment state
        member_role_ids = {r.id for r in member.roles}
        for role in allowed_roles[:25]:  # Discord max buttons per view
            style = discord.ButtonStyle.secondary
            checked = "✅" if role.id in member_role_ids else "☐"
            label = f"{checked} {role.name}"
            self.add_item(RoleToggleButton(role=role, label=label, style=style))


class RoleToggleButton(discord.ui.Button):
    def __init__(self, role: discord.Role, style: discord.ButtonStyle, label: Optional[str] = None):
        super().__init__(label=label or role.name, style=style, custom_id=f"toggle_role:{role.id}")
        self.role = role

    async def callback(self, interaction: Interaction):
        assert interaction.guild is not None
        bot: RoleBot = interaction.client  # type: ignore
        if not bot.is_moderator(interaction.guild.id, interaction.user):
            await interaction.response.send_message("You are not allowed to manage roles.", ephemeral=True)
            return
        member = None
        # message should mention the target user in content
        if interaction.message and interaction.message.mentions:
            member = interaction.message.mentions[0]
        if not isinstance(member, discord.Member):
            await interaction.response.send_message("Could not resolve target member.", ephemeral=True)
            return
        try:
            action = None
            if self.role in member.roles:
                await member.remove_roles(self.role, reason=f"Toggled by {interaction.user} via bot")
                action = "removed"
            else:
                await member.add_roles(self.role, reason=f"Toggled by {interaction.user} via bot")
                action = "assigned"
            # Ack ephemerally
            await interaction.response.send_message(
                f"{action.capitalize()} {self.role.name} {'from' if action=='removed' else 'to'} {member.display_name}.",
                ephemeral=True,
            )
            # Refresh the control panel to reflect new state (checkmarks)
            try:
                bot: RoleBot = interaction.client  # type: ignore
                cfg = bot.get_guild_cfg(member.guild.id)
                allowed_roles = [r for r in member.guild.roles if r.id in set(cfg.allowed_role_ids)]
                new_view = RoleToggleView(member=member, allowed_roles=allowed_roles)
                new_content = bot.build_panel_content(member, allowed_roles)
                if interaction.message:
                    try:
                        await interaction.message.edit(content=new_content, view=new_view, suppress=True)
                    except TypeError:
                        await interaction.message.edit(content=new_content, view=new_view)
            except Exception:
                pass
        except discord.Forbidden:
            await interaction.response.send_message("I don't have permission to manage that role.", ephemeral=True)
        except discord.HTTPException as e:
            await interaction.response.send_message(f"Discord error: {e}", ephemeral=True)


class RoleBot(commands.Bot):
    def __init__(self, settings: Settings):
        super().__init__(command_prefix=commands.when_mentioned_or("/"), intents=INTENTS)
        self.settings = settings
        self.storage = Storage(settings.data_path)

    # Helpers to render panel content with checkmarks
    @staticmethod
    def build_panel_content(member: discord.Member, allowed_roles: List[discord.Role]) -> str:
        member_role_ids = {r.id for r in member.roles}
        lines = [f"New member joined: {member.mention}", "", "Toggle roles for this member using the buttons below.", "", "Current allowed roles:"]
        for r in allowed_roles:
            checked = "✅" if r.id in member_role_ids else "☐"
            lines.append(f"- {checked} {r.name}")
        return "\n".join(lines)

    async def refresh_member_panel(self, member: discord.Member) -> None:
        cfg = self.get_guild_cfg(member.guild.id)
        if not cfg.assignment_channel_id:
            return
        channel = member.guild.get_channel(cfg.assignment_channel_id)
        if not isinstance(channel, discord.TextChannel):
            return
        # find the most recent panel for this member
        try:
            async for m in channel.history(limit=50):
                if m.author.id == self.user.id if self.user else False:  # type: ignore
                    # check mention and components
                    if member in m.mentions and m.components:
                        allowed_roles = [r for r in member.guild.roles if r.id in set(cfg.allowed_role_ids)]
                        view = RoleToggleView(member=member, allowed_roles=allowed_roles)
                        content = self.build_panel_content(member, allowed_roles)
                        try:
                            await m.edit(content=content, view=view, suppress=True)
                        except TypeError:
                            # suppress kw name varies across versions; fallback
                            await m.edit(content=content, view=view)
                        break
        except Exception:
            # ignore refresh errors
            pass

    async def setup_hook(self) -> None:
        # Register command groups
        self.tree.add_command(setup_group)
        self.tree.add_command(admin_group)
        self.tree.add_command(roles_allow_group)
        # Sync commands on startup (guild-specific if restricted)
        if self.settings.allowed_guilds:
            for gid in self.settings.allowed_guilds:
                try:
                    g = Object(id=gid)
                    # Publish global commands instantly to this guild by copying them
                    self.tree.clear_commands(guild=g)
                    self.tree.copy_global_to(guild=g)
                    await self.tree.sync(guild=g)
                except Exception as e:
                    logger.warning("Command sync failed for guild %s: %s", gid, e)
        else:
            await self.tree.sync()

    # Permission helpers
    def get_guild_cfg(self, guild_id: int) -> GuildConfig:
        return self.storage.load_guild(guild_id)

    def is_admin(self, guild_id: int, user: discord.abc.User) -> bool:
        cfg = self.get_guild_cfg(guild_id)
        return cfg.admin_user_id == user.id

    def is_moderator(self, guild_id: int, user: discord.Member | discord.User) -> bool:
        cfg = self.get_guild_cfg(guild_id)
        if cfg.admin_user_id == user.id:
            return True
        if isinstance(user, discord.Member):
            if cfg.moderator_role_id and any(r.id == cfg.moderator_role_id for r in user.roles):
                return True
        return user.id in cfg.moderator_user_ids

    async def ensure_assignment_channel(self, guild: discord.Guild) -> Optional[discord.TextChannel]:
        cfg = self.get_guild_cfg(guild.id)
        if cfg.assignment_channel_id:
            chan = guild.get_channel(cfg.assignment_channel_id)
            if isinstance(chan, discord.TextChannel):
                return chan
        # Create a private channel visible to admin/mod role only
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
        }
        if cfg.moderator_role_id:
            mod_role = guild.get_role(cfg.moderator_role_id)
            if mod_role:
                overwrites[mod_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
        if cfg.admin_user_id:
            admin = guild.get_member(cfg.admin_user_id)
            if admin:
                overwrites[admin] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
        channel = await guild.create_text_channel(name="role-assignments", overwrites=overwrites, reason="Create private role assignment control channel")
        cfg.assignment_channel_id = channel.id
        self.storage.save_guild(cfg)
        return channel

    async def post_assignment_panel(self, member: discord.Member) -> None:
        guild = member.guild
        cfg = self.get_guild_cfg(guild.id)
        channel: Optional[discord.TextChannel] = None
        if cfg.assignment_channel_id:
            ch = guild.get_channel(cfg.assignment_channel_id)
            if isinstance(ch, discord.TextChannel):
                channel = ch
        if not channel:
            channel = await self.ensure_assignment_channel(guild)
        # Build allowed roles list
        allowed_roles = [r for r in guild.roles if r.id in set(cfg.allowed_role_ids)]
        if not allowed_roles:
            content = f"New member joined: {member.mention} (no allowed roles configured yet). Use /roles_allow_add to permit roles."
            await channel.send(content)
            return
        view = RoleToggleView(member=member, allowed_roles=allowed_roles)
        content = self.build_panel_content(member, allowed_roles)
        try:
            msg = await channel.send(content, view=view, silent=True, suppress_embeds=True)
        except TypeError:
            # Older discord.py may not support suppress_embeds kw
            msg = await channel.send(content, view=view, silent=True)
        # Pin message and watch for deletion by recreating if needed isn't directly possible without background task.
        try:
            await msg.pin(reason="Keep role control visible")
        except discord.HTTPException:
            pass


bot_settings = Settings.load()
# Adjust log level
try:
    logging.getLogger().setLevel(getattr(logging, bot_settings.log_level.upper(), logging.INFO))
    logger.setLevel(getattr(logging, bot_settings.log_level.upper(), logging.INFO))
    logging.getLogger("discord").setLevel(logging.WARNING)
except Exception:
    pass

# Singleton lock to avoid duplicate instances during rolling updates
_LOCK_PATH = os.path.join(bot_settings.data_path, ".instance.lock")
_MAX_WAIT = 60  # seconds
_WAIT_STEP = 3
start = time.time()
acquired = False
while time.time() - start < _MAX_WAIT and not acquired:
    try:
        # O_EXCL ensures only one creates it
        fd = os.open(_LOCK_PATH, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(fd)
        acquired = True
    except FileExistsError:
        time.sleep(_WAIT_STEP)

if not acquired:
    logger.warning("Could not acquire singleton lock at %s after %ss; continuing anyway.", _LOCK_PATH, _MAX_WAIT)
else:
    def _release_lock():
        try:
            os.remove(_LOCK_PATH)
        except Exception:
            pass
    atexit.register(_release_lock)

bot = RoleBot(bot_settings)


# Events
@bot.event
async def on_ready():
    logger.info(f"Logged in as {bot.user} ({bot.user.id if bot.user else 'unknown'})")


@bot.event
async def on_member_join(member: discord.Member):
    # Gate by allowed guilds if configured
    if bot.settings.allowed_guilds and member.guild.id not in set(bot.settings.allowed_guilds):
        return
    try:
        await bot.post_assignment_panel(member)
    except Exception as e:
        logger.exception("Failed to post assignment panel: %s", e)


# Checks
async def ensure_admin_if_empty(interaction: Interaction) -> None:
    assert interaction.guild is not None
    cfg = bot.get_guild_cfg(interaction.guild.id)
    if cfg.admin_user_id is None:
        cfg.admin_user_id = interaction.user.id
        bot.storage.save_guild(cfg)
        try:
            await interaction.user.send(f"You have been set as the initial admin for {interaction.guild.name}.")
        except Exception:
            pass


def admin_only(interaction: Interaction) -> bool:
    if not interaction.guild:
        return False
    # Gate by allowed guilds if configured
    if bot.settings.allowed_guilds and interaction.guild.id not in set(bot.settings.allowed_guilds):
        return False
    return bot.is_admin(interaction.guild.id, interaction.user)


def moderator_only(interaction: Interaction) -> bool:
    if not interaction.guild:
        return False
    # Gate by allowed guilds if configured
    if bot.settings.allowed_guilds and interaction.guild.id not in set(bot.settings.allowed_guilds):
        return False
    return bot.is_moderator(interaction.guild.id, interaction.user)  # type: ignore


# Command groups
setup_group = app_commands.Group(name="setup", description="Server setup commands")
admin_group = app_commands.Group(name="admin", description="Admin commands")
roles_allow_group = app_commands.Group(name="roles_allow", description="Manage allowed roles")


@setup_group.command(name="set_moderator_role", description="Set a Discord role that grants moderator permissions for this bot.")
@app_commands.describe(role="Role that should act as moderator")
async def set_moderator_role(interaction: Interaction, role: discord.Role):
    await ensure_admin_if_empty(interaction)
    if not admin_only(interaction):
        await interaction.response.send_message("Only the admin can set the moderator role.", ephemeral=True)
        return
    cfg = bot.get_guild_cfg(interaction.guild.id)  # type: ignore
    cfg.moderator_role_id = role.id
    bot.storage.save_guild(cfg)
    await interaction.response.send_message(f"Moderator role set to {role.name}.", ephemeral=True)


@setup_group.command(name="set_assignment_channel", description="Set or create the private assignment control channel.")
@app_commands.describe(channel="Existing text channel to use; leave empty to create a private one")
async def set_assignment_channel(interaction: Interaction, channel: Optional[discord.TextChannel] = None):
    await ensure_admin_if_empty(interaction)
    if not admin_only(interaction):
        await interaction.response.send_message("Only the admin can set the assignment channel.", ephemeral=True)
        return
    cfg = bot.get_guild_cfg(interaction.guild.id)  # type: ignore
    if channel:
        cfg.assignment_channel_id = channel.id
        bot.storage.save_guild(cfg)
        await interaction.response.send_message(f"Assignment channel set to {channel.mention}.", ephemeral=True)
    else:
        ch = await bot.ensure_assignment_channel(interaction.guild)  # type: ignore
        await interaction.response.send_message(f"Assignment channel created/ensured: {ch.mention}.", ephemeral=True)


@admin_group.command(name="add_moderator", description="Grant moderator permission to a user")
@app_commands.describe(user="User to grant moderator permissions")
async def add_moderator(interaction: Interaction, user: discord.User):
    await ensure_admin_if_empty(interaction)
    if not admin_only(interaction):
        await interaction.response.send_message("Only the admin can add moderators.", ephemeral=True)
        return
    cfg = bot.get_guild_cfg(interaction.guild.id)  # type: ignore
    if user.id not in cfg.moderator_user_ids:
        cfg.moderator_user_ids.append(user.id)
        bot.storage.save_guild(cfg)
    await interaction.response.send_message(f"{user.mention} is now a moderator.", ephemeral=True)


@admin_group.command(name="remove_moderator", description="Revoke moderator permission from a user")
@app_commands.describe(user="User to revoke moderator permissions")
async def remove_moderator(interaction: Interaction, user: discord.User):
    await ensure_admin_if_empty(interaction)
    if not admin_only(interaction):
        await interaction.response.send_message("Only the admin can remove moderators.", ephemeral=True)
        return
    cfg = bot.get_guild_cfg(interaction.guild.id)  # type: ignore
    if user.id in cfg.moderator_user_ids:
        cfg.moderator_user_ids.remove(user.id)
        bot.storage.save_guild(cfg)
    await interaction.response.send_message(f"{user.mention} is no longer a moderator.", ephemeral=True)


@admin_group.command(name="list_moderators", description="List moderators")
async def list_moderators(interaction: Interaction):
    await ensure_admin_if_empty(interaction)
    if not moderator_only(interaction):
        await interaction.response.send_message("Not permitted.", ephemeral=True)
        return
    cfg = bot.get_guild_cfg(interaction.guild.id)  # type: ignore
    names = []
    if interaction.guild:
        for uid in cfg.moderator_user_ids:
            m = interaction.guild.get_member(uid)
            names.append(m.mention if m else f"<@{uid}>")
    await interaction.response.send_message("Moderators: " + (", ".join(names) if names else "none"), ephemeral=True)


@admin_group.command(name="resync", description="Force re-sync of slash commands for this guild or globally")
async def admin_resync(interaction: Interaction):
    await ensure_admin_if_empty(interaction)
    if not admin_only(interaction):
        await interaction.response.send_message("Only the admin can resync commands.", ephemeral=True)
        return
    # Defer to avoid interaction timeout during potentially long sync
    try:
        await interaction.response.defer(ephemeral=True, thinking=True)
    except Exception:
        # Ignore if already deferred or responded for some reason
        pass
    try:
        if bot.settings.allowed_guilds:
            # sync only to configured guilds and copy global commands so they appear instantly
            for gid in bot.settings.allowed_guilds:
                try:
                    g = Object(id=gid)
                    bot.tree.clear_commands(guild=g)
                    bot.tree.copy_global_to(guild=g)
                    await bot.tree.sync(guild=g)
                except Exception as e:
                    logger.warning("Resync failed for guild %s: %s", gid, e)
        else:
            await bot.tree.sync()
        await interaction.followup.send("Commands resynced.")
    except Exception as e:
        await interaction.followup.send(f"Resync failed: {e}")


@admin_group.command(name="simulate_rejoin", description="Simulate a member rejoining (posts the control panel) [mods/admin]")
@app_commands.describe(member="Member to simulate as newly joined")
async def admin_simulate_rejoin(interaction: Interaction, member: discord.Member):
    # Same logic as the top-level /simulate_rejoin, provided here under /admin for better discoverability
    await ensure_admin_if_empty(interaction)
    if not moderator_only(interaction):
        await interaction.response.send_message("Not permitted.", ephemeral=True)
        return
    if not interaction.guild or member.guild.id != interaction.guild.id:
        await interaction.response.send_message("Target member must be from this server.", ephemeral=True)
        return
    if member.bot:
        await interaction.response.send_message("Cannot simulate rejoin for bot users.", ephemeral=True)
        return
    try:
        await bot.post_assignment_panel(member)
        await interaction.response.send_message(f"Simulated rejoin for {member.mention}. Panel posted in the assignment channel.", ephemeral=True)
    except Exception as e:
        logger.exception("admin simulate_rejoin failed: %s", e)
        await interaction.response.send_message(f"Failed to simulate rejoin: {e}", ephemeral=True)


@roles_allow_group.command(name="add", description="Allow a role to be assigned via the bot")
@app_commands.describe(role="Role to allow")
async def roles_allow_add(interaction: Interaction, role: discord.Role):
    await ensure_admin_if_empty(interaction)
    if not admin_only(interaction):
        await interaction.response.send_message("Only the admin can manage allowed roles.", ephemeral=True)
        return
    cfg = bot.get_guild_cfg(interaction.guild.id)  # type: ignore
    if role.managed:
        await interaction.response.send_message("Cannot allow a managed role.", ephemeral=True)
        return
    if role.id not in cfg.allowed_role_ids:
        cfg.allowed_role_ids.append(role.id)
        bot.storage.save_guild(cfg)
    await interaction.response.send_message(f"Allowed role: {role.name}", ephemeral=True)


@roles_allow_group.command(name="remove", description="Remove a role from allowed list")
@app_commands.describe(role="Role to disallow")
async def roles_allow_remove(interaction: Interaction, role: discord.Role):
    await ensure_admin_if_empty(interaction)
    if not admin_only(interaction):
        await interaction.response.send_message("Only the admin can manage allowed roles.", ephemeral=True)
        return
    cfg = bot.get_guild_cfg(interaction.guild.id)  # type: ignore
    if role.id in cfg.allowed_role_ids:
        cfg.allowed_role_ids.remove(role.id)
        bot.storage.save_guild(cfg)
    await interaction.response.send_message(f"Disallowed role: {role.name}", ephemeral=True)


@roles_allow_group.command(name="list", description="List allowed roles")
async def roles_allow_list(interaction: Interaction):
    await ensure_admin_if_empty(interaction)
    if not moderator_only(interaction):
        await interaction.response.send_message("Not permitted.", ephemeral=True)
        return
    cfg = bot.get_guild_cfg(interaction.guild.id)  # type: ignore
    roles = []
    if interaction.guild:
        for rid in cfg.allowed_role_ids:
            r = interaction.guild.get_role(rid)
            if r:
                roles.append(r.mention)
    await interaction.response.send_message("Allowed roles: " + (", ".join(roles) if roles else "none"), ephemeral=True)


@bot.tree.command(name="assign", description="Assign an allowed role to a member")
@app_commands.describe(member="Member to assign", role="Role to assign")
async def assign(interaction: Interaction, member: discord.Member, role: discord.Role):
    await ensure_admin_if_empty(interaction)
    if not moderator_only(interaction):
        await interaction.response.send_message("Not permitted.", ephemeral=True)
        return
    cfg = bot.get_guild_cfg(interaction.guild.id)  # type: ignore
    if role.id not in cfg.allowed_role_ids:
        await interaction.response.send_message("That role is not in the allowed list.", ephemeral=True)
        return
    try:
        await member.add_roles(role, reason=f"Assigned by {interaction.user} via bot")
        await interaction.response.send_message(f"Assigned {role.name} to {member.display_name}.", ephemeral=True)
        try:
            await bot.refresh_member_panel(member)
        except Exception:
            pass
    except discord.Forbidden:
        await interaction.response.send_message("I don't have permission to manage that role.", ephemeral=True)


@bot.tree.command(name="remove", description="Remove an allowed role from a member")
@app_commands.describe(member="Member to remove from role", role="Role to remove")
async def remove(interaction: Interaction, member: discord.Member, role: discord.Role):
    await ensure_admin_if_empty(interaction)
    if not moderator_only(interaction):
        await interaction.response.send_message("Not permitted.", ephemeral=True)
        return
    cfg = bot.get_guild_cfg(interaction.guild.id)  # type: ignore
    if role.id not in cfg.allowed_role_ids:
        await interaction.response.send_message("That role is not in the allowed list.", ephemeral=True)
        return
    try:
        await member.remove_roles(role, reason=f"Removed by {interaction.user} via bot")
        await interaction.response.send_message(f"Removed {role.name} from {member.display_name}.", ephemeral=True)
        try:
            await bot.refresh_member_panel(member)
        except Exception:
            pass
    except discord.Forbidden:
        await interaction.response.send_message("I don't have permission to manage that role.", ephemeral=True)


@bot.tree.command(name="simulate_rejoin", description="Simulate a member rejoining to test the control panel posting (mods only)")
@app_commands.describe(member="Member to simulate as newly joined")
async def simulate_rejoin(interaction: Interaction, member: discord.Member):
    await ensure_admin_if_empty(interaction)
    if not moderator_only(interaction):
        await interaction.response.send_message("Not permitted.", ephemeral=True)
        return
    # Only allow simulating for the current guild and non-bots
    if not interaction.guild or member.guild.id != interaction.guild.id:
        await interaction.response.send_message("Target member must be from this server.", ephemeral=True)
        return
    if member.bot:
        await interaction.response.send_message("Cannot simulate rejoin for bot users.", ephemeral=True)
        return
    try:
        await bot.post_assignment_panel(member)
        await interaction.response.send_message(f"Simulated rejoin for {member.mention}. Panel posted in the assignment channel.", ephemeral=True)
    except Exception as e:
        logger.exception("simulate_rejoin failed: %s", e)
        await interaction.response.send_message(f"Failed to simulate rejoin: {e}", ephemeral=True)


if __name__ == "__main__":
    token = bot_settings.token
    bot.run(token)  # type: ignore
