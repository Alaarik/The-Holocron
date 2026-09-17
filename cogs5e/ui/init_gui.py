import disnake
from utils.argparser import argparse


class AddMonsterModal(disnake.ui.Modal):
    def __init__(self, bot, dashboard_view):
        self.bot = bot
        self.dashboard_view = dashboard_view
        components = [
            disnake.ui.TextInput(
                label="Monster Name",
                placeholder="e.g. Stormtrooper, B1 Battle Droid",
                custom_id="monster_name",
                style=disnake.TextInputStyle.short,
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
            
        init_cog = self.bot.get_cog("Initiative")
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
        except Exception as _e:
            import traceback; traceback.print_exc()
            return await interaction.response.send_message(f"No active combat found. Error: {_e}", ephemeral=True)
            
        if not combat.can_edit(interaction.author):
            return await interaction.response.send_message("You are not the DM of this combat.", ephemeral=True)
            
        await interaction.response.defer()
        
        try:
            msgs = await combat.next_turn(interaction)
        except Exception as e:
            msgs = [str(e)]
            
        await combat.commit(interaction)
        await interaction.followup.send("\n".join(msgs))
        
        summary = combat.get_summary()
        try:
            await interaction.message.edit(content=summary, view=self)
        except Exception as _e:
            import traceback; traceback.print_exc()
            return await interaction.response.send_message(f"No active combat found. Error: {_e}", ephemeral=True)
            
        await interaction.response.send_modal(AddMonsterModal(self.bot, self))

    @disnake.ui.button(label="Refresh", style=disnake.ButtonStyle.secondary, custom_id="init_refresh")
    async def refresh(self, button: disnake.ui.Button, interaction: disnake.MessageInteraction):
        from cogs5e.initiative import Combat
        try:
            combat = await Combat.from_ctx(interaction)
        except Exception as _e:
            import traceback; traceback.print_exc()
            return await interaction.response.send_message(f"No active combat found. Error: {_e}", ephemeral=True)
            
        await interaction.response.defer()
        
        summary = combat.get_summary()
        try:
            await interaction.message.edit(content=summary, view=self)
        except Exception as _e:
            import traceback; traceback.print_exc()
            return await interaction.response.send_message(f"No active combat found. Error: {_e}", ephemeral=True)
            
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
