import disnake
from disnake.ext import commands
from utils.argparser import argparse
from cogs5e.ui.init_gui import CombatDashboardView
from cogs5e.ui.combat_gui import CombatView

class InitSlashCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
    @commands.slash_command(name="init", description="Combat Initiative Commands")
    async def slash_init(self, inter: disnake.ApplicationCommandInteraction):
        pass
        
    @slash_init.sub_command(name="start", description="Starts a new combat tracker and spawns the dashboard.")
    async def init_start(self, inter: disnake.ApplicationCommandInteraction):
        await inter.response.defer()
        
        from cogs5e.initiative import Combat, CombatOptions
        
        try:
            await Combat.ensure_unique_chan(inter)
        except Exception as e:
            return await inter.followup.send("There is already an active combat in this channel.", ephemeral=True)
            
        options = CombatOptions()
        
        temp_summary_msg = await inter.followup.send("```Awaiting combatants...```", wait=True)
        
        combat = Combat.new(
            channel_id=str(inter.channel.id),
            message_id=temp_summary_msg.id,
            dm_id=inter.author.id,
            options=options,
            ctx=inter,
        )
        
        try:
            await temp_summary_msg.pin()
        except:
            pass
            
        out = (
            "Combat has begun!\n"
            "Use the Dashboard buttons below to proceed or use slash commands to manage combat."
        )
        await temp_summary_msg.edit(content=combat.get_summary(), view=CombatDashboardView(self.bot))
        await inter.followup.send(out)

    @slash_init.sub_command(name="next", description="Move to the next turn.")
    async def init_next(self, inter: disnake.ApplicationCommandInteraction):
        await inter.response.defer()
        from cogs5e.initiative import Combat
        try:
            combat = await Combat.from_ctx(inter)
        except Exception:
            return await inter.followup.send("No active combat found.", ephemeral=True)
            
        if not combat.can_edit(inter.author):
            return await inter.followup.send("You are not the DM of this combat.", ephemeral=True)
            
        try:
            msgs = await combat.next_turn(inter)
            await combat.commit()
            await inter.followup.send("\n".join(msgs))
        except Exception as e:
            await inter.followup.send(str(e))
            
        try:
            msg = await inter.channel.fetch_message(combat.summary_message_id)
            await msg.edit(content=combat.get_summary(), view=CombatDashboardView(self.bot))
        except:
            pass

    @slash_init.sub_command(name="hp", description="Modify the HP of a combatant.")
    async def init_hp(
        self, 
        inter: disnake.ApplicationCommandInteraction, 
        target: str = commands.Param(description="The combatant to modify."),
        amount: int = commands.Param(description="The amount of HP to change (negative for damage).")
    ):
        await inter.response.defer()
        from cogs5e.initiative import Combat
        try:
            combat = await Combat.from_ctx(inter)
        except Exception:
            return await inter.followup.send("No active combat found.", ephemeral=True)
            
        if not combat.can_edit(inter.author):
            return await inter.followup.send("You are not the DM of this combat.", ephemeral=True)
            
        target_combatant = combat.get_combatant(target)
        if not target_combatant:
            return await inter.followup.send("Target not found.", ephemeral=True)
            
        if target_combatant.hp is None:
            target_combatant.set_hp(0)
            
        target_combatant.modify_hp(amount)
        await combat.commit()
        await inter.followup.send(f"Modified {target}'s HP by {amount}.")
        
        try:
            msg = await inter.channel.fetch_message(combat.summary_message_id)
            await msg.edit(content=combat.get_summary(), view=CombatDashboardView(self.bot))
        except:
            pass
            
    @init_hp.autocomplete("target")
    async def init_hp_target_auto(self, inter: disnake.ApplicationCommandInteraction, user_input: str):
        from cogs5e.initiative import Combat
        try:
            combat = await Combat.from_ctx(inter)
            if not combat: return []
        except: return []
        choices = [c.name for c in combat.combatants if user_input.lower() in c.name.lower()]
        return choices[:25]



    @slash_init.sub_command(name="remove_effect", description="Removes a condition or effect from a combatant.")
    async def init_remove_effect(
        self,
        inter: disnake.ApplicationCommandInteraction,
        target: str = commands.Param(description="The combatant with the effect."),
        effect: str = commands.Param(description="The effect to remove.")
    ):
        await inter.response.defer()
        from cogs5e.initiative import Combat
        try:
            combat = await Combat.from_ctx(inter)
        except:
            return await inter.followup.send("No active combat found.", ephemeral=True)
            
        if not combat.can_edit(inter.author):
            return await inter.followup.send("You are not the DM of this combat.", ephemeral=True)
            
        target_combatant = combat.get_combatant(target)
        if not target_combatant:
            return await inter.followup.send("Target not found.", ephemeral=True)
            
        effect_obj = target_combatant.get_effect(effect)
        if not effect_obj:
            return await inter.followup.send(f"Effect '{effect}' not found on {target}.", ephemeral=True)
            
        target_combatant.remove_effect(effect_obj)
        await combat.commit()
        await inter.followup.send(f"Removed '{effect}' from {target}.")
        
        try:
            msg = await inter.channel.fetch_message(combat.summary_message_id)
            await msg.edit(content=combat.get_summary(), view=CombatDashboardView(self.bot))
        except:
            pass

    @init_remove_effect.autocomplete("target")
    async def init_remove_target_auto(self, inter: disnake.ApplicationCommandInteraction, user_input: str):
        from cogs5e.initiative import Combat
        try:
            combat = await Combat.from_ctx(inter)
            if not combat: return []
        except: return []
        choices = [c.name for c in combat.combatants if user_input.lower() in c.name.lower()]
        return choices[:25]
        
    @init_remove_effect.autocomplete("effect")
    async def init_remove_effect_auto(self, inter: disnake.ApplicationCommandInteraction, user_input: str, target: str = ""):
        from cogs5e.initiative import Combat
        try:
            combat = await Combat.from_ctx(inter)
            if not combat: return []
            c = combat.get_combatant(target)
            if not c: return []
        except: return []
        choices = [eff.name for eff in c.effects if user_input.lower() in eff.name.lower()]
        return choices[:25]


    @slash_init.sub_command(name="attack", description="Make an attack as a combatant.")
    async def init_attack(
        self,
        inter: disnake.ApplicationCommandInteraction,
        attacker: str = commands.Param(description="The combatant making the attack."),
        weapon: str = commands.Param(description="The weapon or attack to use."),
        target: str = commands.Param(description="The target of the attack.", default="")
    ):
        from cogs5e.initiative import Combat
        from cogs5e.ui.combat_gui import CombatView
        try:
            combat = await Combat.from_ctx(inter)
        except:
            return await inter.response.send_message("No active combat found.", ephemeral=True)
            
        attacker_combatant = combat.get_combatant(attacker)
        if not attacker_combatant:
            return await inter.response.send_message("Attacker not found in combat.", ephemeral=True)
            
        # Verify permissions
        if not combat.can_edit(inter.author) and attacker_combatant.controller_id != inter.author.id:
            return await inter.response.send_message("You do not have permission to control this combatant.", ephemeral=True)
            
        atk = attacker_combatant.get_attack(weapon)
        if not atk:
            return await inter.response.send_message(f"Attack '{weapon}' not found on {attacker}.", ephemeral=True)

        # For monsters, they generally don't have these specific modifiers, but we pass them to CombatView anyway.
        # CombatView expects a 'Character' object with 'attacks'. PlayerCombatant/MonsterCombatant have '.attacks'.
        # However, CombatView uses `character.levels` for scaling (Sneak attack etc).
        # To avoid breaking CombatView, we will bypass it for monsters and just roll immediately for now, OR 
        # mock it.
        # Since this is mainly for GM monsters, let's just roll the attack directly to save time and clicks!
        
        await inter.response.defer()
        from cogs5e.utils.actionutils import run_attack
        from cogs5e.models.sheet.statblock import StatBlock
        from utils.argparser import argparse
        
        args_str = ""
        if target:
            args_str += f"-t \"{target}\""
            
        args = argparse(args_str)
        embed = disnake.Embed()
        
        target_list = []
        if target:
            t = combat.get_combatant(target)
            if t: target_list = [t]
            
        await run_attack(
            ctx=inter,
            embed=embed,
            args=args,
            caster=attacker_combatant,
            attack=atk,
            targets=target_list,
            combat=combat
        )
        
        await inter.followup.send(embed=embed)

    @init_attack.autocomplete("attacker")
    async def init_attack_attacker_auto(self, inter: disnake.ApplicationCommandInteraction, user_input: str):
        from cogs5e.initiative import Combat
        try:
            combat = await Combat.from_ctx(inter)
            if not combat: return []
        except: return []
        choices = [c.name for c in combat.combatants if user_input.lower() in c.name.lower()]
        return choices[:25]
        
    @init_attack.autocomplete("weapon")
    async def init_attack_weapon_auto(self, inter: disnake.ApplicationCommandInteraction, user_input: str, attacker: str = ""):
        from cogs5e.initiative import Combat
        try:
            combat = await Combat.from_ctx(inter)
            if not combat: return []
            c = combat.get_combatant(attacker)
            if not c: return []
        except: return []
        choices = []
        for atk in c.attacks:
            if user_input.lower() in atk.name.lower():
                choices.append(atk.name)
        return choices[:25]
        
    @init_attack.autocomplete("target")
    async def init_attack_target_auto(self, inter: disnake.ApplicationCommandInteraction, user_input: str, attacker: str = "", weapon: str = ""):
        from cogs5e.initiative import Combat
        try:
            combat = await Combat.from_ctx(inter)
            if not combat: return []
        except: return []
        choices = [c.name for c in combat.combatants if user_input.lower() in c.name.lower()]
        return choices[:25]


    @slash_init.sub_command(name="add", description="Add a monster to the active combat.")
    async def init_add(
        self,
        inter: disnake.ApplicationCommandInteraction,
        monster_name: str = commands.Param(description="The name of the monster to add.")
    ):
        await inter.response.defer()
        from cogs5e.initiative import Combat
        try:
            combat = await Combat.from_ctx(inter)
            if not combat:
                return await inter.followup.send("No active combat found.", ephemeral=True)
        except Exception as e:
            return await inter.followup.send("No active combat found.", ephemeral=True)
            
        if not combat.can_edit(inter.author):
            return await inter.followup.send("You are not the DM of this combat.", ephemeral=True)
            
        # Import the madd function from initiative cog
        init_cog = self.bot.get_cog("Initiative")
        if not init_cog:
            return await inter.followup.send("Initiative module is not loaded.", ephemeral=True)
            
        # Fake a context to run the madd command directly
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
            await init_cog.madd(ctx, monster_name=monster_name)
        except Exception as e:
            await inter.followup.send(f"Error adding monster: {e}")
            
        # Update dashboard
        try:
            msg = await inter.channel.fetch_message(combat.summary_message_id)
            await msg.edit(content=combat.get_summary(), view=CombatDashboardView(self.bot))
        except:
            pass


def setup(bot):
    bot.add_cog(InitSlashCog(bot))
