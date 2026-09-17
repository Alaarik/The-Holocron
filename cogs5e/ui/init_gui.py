import disnake
from utils.argparser import argparse

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
            
        if not combat.can_edit(interaction.author):
            return await interaction.response.send_message("You are not the DM of this combat.", ephemeral=True)
            
        await interaction.response.defer()
        
        try:
            msgs = await combat.next_turn(interaction)
        except Exception as e:
            msgs = [str(e)]
            
        await combat.commit()
        await interaction.followup.send("\n".join(msgs))
        
        summary = combat.get_summary()
        try:
            await interaction.message.edit(content=summary, view=self)
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
            r = roll(f"1d20+{character.stats.dexterity.modifier}")
            combatant = PlayerCombatant.from_character(character, interaction, combat, interaction.author.id, r.total, False)
            await combat.add_combatant(combatant, interaction)
            await combat.commit()
            await interaction.followup.send(f"{character.name} joined combat! (Initiative: {r.total})")
            
            summary = combat.get_summary()
            await interaction.message.edit(content=summary, view=self)
        except Exception as e:
            await interaction.followup.send(f"Failed to join: {e}", ephemeral=True)
            
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
            
        if not combat.can_edit(interaction.author):
            return await interaction.response.send_message("You are not the DM of this combat.", ephemeral=True)
            
        await interaction.response.defer()
        try:
            await combat.delete()
        except:
            pass
            
        try:
            await interaction.message.edit(content="Combat has ended.", view=None)
        except:
            pass
