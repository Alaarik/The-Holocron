import disnake
from utils.argparser import argparse


class AddMonsterModal(disnake.ui.Modal):
    def __init__(self, bot, dashboard_view):
        self.bot = bot
        self.dashboard_view = dashboard_view
        components = [
            disnake.ui.TextInput(
                label="Monster Name",
                placeholder="e.g. Trooper, Squad",
                custom_id="monster_name",
                style=disnake.TextInputStyle.short,
                max_length=50,
            ),
            disnake.ui.TextInput(
                label="Custom Name (Optional)",
                placeholder="e.g. Stormtrooper (replaces combat name)",
                custom_id="custom_name",
                style=disnake.TextInputStyle.short,
                required=False,
                max_length=50,
            ),
            disnake.ui.TextInput(
                label="Quantity (Optional)",
                placeholder="e.g. 1, 5, 2d4",
                custom_id="monster_qty",
                style=disnake.TextInputStyle.short,
                required=False,
                max_length=10,
            ),
        ]
        super().__init__(title="Add Monster to Combat", components=components)

    async def callback(self, inter: disnake.ModalInteraction):
        await inter.response.defer()
        monster_name = inter.text_values["monster_name"]
        qty = inter.text_values.get("monster_qty") or "1"
        
        args_str = ""
        if qty and qty != "1":
            args_str += f" -n {qty}"
            
        init_cog = self.bot.get_cog("InitTracker")
        if not init_cog:
            return await inter.followup.send("Initiative module is not loaded.", ephemeral=True)
            
        class FakeCtx:
            def __init__(self, inter):
                self.author = inter.author
                self.channel = inter.channel
                self.guild = inter.guild
                self.bot = inter.bot
                
            async def send(self, *args, **kwargs):
                await inter.followup.send(*args, **kwargs)
                
            async def trigger_typing(self):
                pass
                
            @property
            def clean_prefix(self):
                return "/"
                
        ctx = FakeCtx(inter)
        try:
            await init_cog.madd(ctx, monster_name=monster_name, args=args_str)
        except Exception as e:
            await inter.followup.send(f"Error adding monster: {e}")
            
        from cogs5e.initiative import Combat
        try:
            combat = await Combat.from_ctx(inter)
            summary = combat.get_summary()
            await inter.message.edit(content=summary, view=self.dashboard_view)
        except Exception:
            pass


class CombatDashboardView(disnake.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @disnake.ui.button(label="Next Turn", style=disnake.ButtonStyle.primary, custom_id="init_next_turn")
    async def next_turn(self, button: disnake.ui.Button, interaction: disnake.MessageInteraction):
        from cogs5e.initiative import Combat
        try:
            combat = await Combat.from_ctx(interaction)
        except Exception:
            return await interaction.response.send_message("No active combat found.", ephemeral=True)
            
        if combat.dm_id != interaction.author.id and not interaction.permissions.manage_messages:
            return await interaction.response.send_message("You are not the DM of this combat.", ephemeral=True)
            
        await interaction.response.defer()
        
        init_cog = self.bot.get_cog("InitTracker")
        class FakeCtx:
            def __init__(self, inter, c):
                self.author = inter.author
                self.channel = inter.channel
                self.guild = inter.guild
                self.bot = inter.bot
                self._combat = c
            async def get_combat(self):
                return self._combat
            async def get_server_settings(self):
                from utils.settings.guild import ServerSettings
                return await ServerSettings.from_ctx(self)
            async def send(self, *args, **kwargs):
                await interaction.followup.send(*args, **kwargs)
        
        ctx = FakeCtx(interaction, combat)
        try:
            await init_cog.init_next.callback(init_cog, ctx)
        except Exception as e:
            await interaction.followup.send(f"Error advancing turn: {e}")
            
        # The combat summary will be updated by init_next itself sending the turn message,
        # but we can also update the dashboard view.
        try:
            combat = await Combat.from_ctx(interaction)
            await interaction.message.edit(content=combat.get_summary(), view=self)
        except Exception:
            pass

    @disnake.ui.button(label="Join Combat", style=disnake.ButtonStyle.success, custom_id="init_join")
    async def join_combat(self, button: disnake.ui.Button, interaction: disnake.MessageInteraction):
        await interaction.response.defer()
        
        # Pull logic equivalent to !init join
        from cogs5e.models.character import Character
        from cogs5e.initiative.combatant import PlayerCombatant
        from cogs5e.initiative import Combat
        from utils.argparser import ParsedArguments
        
        try:
            character = await Character.from_ctx(interaction, use_global=True, use_guild=True, use_channel=True)
        except Exception:
            return await interaction.followup.send("You do not have an active character.", ephemeral=True)
            
        try:
            combat = await Combat.from_ctx(interaction)
        except Exception:
            return await interaction.followup.send("No active combat found.", ephemeral=True)
            
        if combat.get_combatant(character.name):
            return await interaction.followup.send("Your character is already in combat.", ephemeral=True)
            
        try:
            import random
            from d20 import roll
            
            # Use their dex mod for init, handling adv/dis if they use args. Here we just do normal roll for button.
            r = roll(f"1d20+{character.stats.get_mod('dex')}")
            combatant = PlayerCombatant.from_character(character, interaction, combat, interaction.author.id, r.total, False)
            combat.add_combatant(combatant)
            await combat.commit(interaction)
            await interaction.followup.send(f"{character.name} joined combat! (Initiative: {r.total})")
            
            summary = combat.get_summary()
            await interaction.message.edit(content=summary, view=self)
        except Exception as e:
            await interaction.followup.send(f"Failed to join: {e}", ephemeral=True)
            

    @disnake.ui.button(label="Add Monster", style=disnake.ButtonStyle.primary, custom_id="init_add_monster")
    async def add_monster(self, button: disnake.ui.Button, interaction: disnake.MessageInteraction):
        from cogs5e.initiative import Combat
        try:
            combat = await Combat.from_ctx(interaction)
            if combat.dm_id != interaction.author.id and not interaction.permissions.manage_messages:
                return await interaction.response.send_message("You are not the DM of this combat.", ephemeral=True)
        except Exception:
            return await interaction.response.send_message("No active combat found.", ephemeral=True)
            
        await interaction.response.send_modal(AddMonsterModal(self.bot, self))

    @disnake.ui.button(label="Refresh", style=disnake.ButtonStyle.secondary, custom_id="init_refresh")
    async def refresh(self, button: disnake.ui.Button, interaction: disnake.MessageInteraction):
        from cogs5e.initiative import Combat
        try:
            combat = await Combat.from_ctx(interaction)
        except Exception:
            return await interaction.response.send_message("No active combat found.", ephemeral=True)
            
        await interaction.response.defer()
        
        summary = combat.get_summary()
        try:
            await interaction.message.edit(content=summary, view=self)
        except Exception:
            pass
            
    @disnake.ui.button(label="End Combat", style=disnake.ButtonStyle.danger, custom_id="init_end")
    async def end_combat(self, button: disnake.ui.Button, interaction: disnake.MessageInteraction):
        from cogs5e.initiative import Combat
        try:
            combat = await Combat.from_ctx(interaction)
        except Exception:
            return await interaction.response.send_message("No active combat found.", ephemeral=True)
            
        if combat.dm_id != interaction.author.id and not interaction.permissions.manage_messages:
            return await interaction.response.send_message("You are not the DM of this combat.", ephemeral=True)
            
        await interaction.response.defer()
        try:
            await combat.end()
        except:
            pass
            
        try:
            await interaction.message.edit(content="Combat has ended.", view=None)
        except:
            pass
