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
        await combat.commit(inter)
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
            
        if combat.dm_id != inter.author.id and not inter.permissions.manage_messages:
            return await inter.followup.send("You are not the DM of this combat.", ephemeral=True)
            
        try:
            msgs = await combat.next_turn(inter)
            await combat.commit(inter)
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
            
        if combat.dm_id != inter.author.id and not inter.permissions.manage_messages:
            return await inter.followup.send("You are not the DM of this combat.", ephemeral=True)
            
        target_combatant = combat.get_combatant(target)
        if not target_combatant:
            return await inter.followup.send("Target not found.", ephemeral=True)
            
        if target_combatant.hp is None:
            target_combatant.set_hp(0)
            
        target_combatant.modify_hp(amount)
        await combat.commit(inter)
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
            
        if combat.dm_id != inter.author.id and not inter.permissions.manage_messages:
            return await inter.followup.send("You are not the DM of this combat.", ephemeral=True)
            
        target_combatant = combat.get_combatant(target)
        if not target_combatant:
            return await inter.followup.send("Target not found.", ephemeral=True)
            
        effect_obj = target_combatant.get_effect(effect)
        if not effect_obj:
            return await inter.followup.send(f"Effect '{effect}' not found on {target}.", ephemeral=True)
            
        target_combatant.remove_effect(effect_obj)
        await combat.commit(inter)
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
            
            # If target is specified, only return their effects
            if target:
                c = combat.get_combatant(target)
                if c:
                    choices = [eff.name for eff in c.get_effects() if user_input.lower() in eff.name.lower()]
                    return list(dict.fromkeys(choices))[:25]
            
            # If no target specified yet, return all effects on ANY combatant
            all_effects = []
            for c in combat.combatants:
                for eff in c.get_effects():
                    if user_input.lower() in eff.name.lower():
                        all_effects.append(eff.name)
            
            # remove duplicates while preserving order
            return list(dict.fromkeys(all_effects))[:25]
        except: return []


    @slash_init.sub_command(name="action", description="Take an action, bonus action, or attack.")
    async def init_action(
        self,
        inter: disnake.ApplicationCommandInteraction,
        attacker: str = commands.Param(description="The combatant making the attack."),
        action: str = commands.Param(description="The action, feature, or weapon to use."),
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
        if combat.dm_id != inter.author.id and attacker_combatant.controller_id != inter.author.id:
            return await inter.response.send_message("You do not have permission to control this combatant.", ephemeral=True)
            
        atk = attacker_combatant.get_attack(action)
        if not atk:
            return await inter.response.send_message(f"Action '{action}' not found on {attacker}.", ephemeral=True)

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

    @init_action.autocomplete("attacker")
    async def init_attack_attacker_auto(self, inter: disnake.ApplicationCommandInteraction, user_input: str):
        from cogs5e.initiative import Combat
        try:
            combat = await Combat.from_ctx(inter)
            if not combat: return []
        except: return []
        choices = [c.name for c in combat.combatants if user_input.lower() in c.name.lower()]
        return choices[:25]
        
    @init_action.autocomplete("action")
    async def init_attack_weapon_auto(self, inter: disnake.ApplicationCommandInteraction, user_input: str, attacker: str = ""):
        from cogs5e.initiative import Combat
        try:
            combat = await Combat.from_ctx(inter)
            if not combat: return []
            c = combat.get_combatant(attacker)
            if not c: return []
        except: return []
        choices = []
        pools = [c.attacks]
        if hasattr(c, "actions") and c.actions:
            pools.append(c.actions)
        elif hasattr(c, "character") and hasattr(c.character, "actions") and c.character.actions:
            pools.append(c.character.actions)
            
        for pool in pools:
            for atk in pool:
                if user_input.lower() in atk.name.lower():
                    if atk.name not in choices:
                        choices.append(atk.name)
        return choices[:25]
        
    @init_action.autocomplete("target")
    async def init_attack_target_auto(self, inter: disnake.ApplicationCommandInteraction, user_input: str, attacker: str = "", action: str = ""):
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
        monster_name: str = commands.Param(description="The name of the monster to add."),
        number: str = commands.Param(description="Number of monsters to add", default=None),
        name: str = commands.Param(description="Custom name for the monster(s)", default=None),
        position: int = commands.Param(description="Initiative position to place them at", default=None)
    ):
        await inter.response.defer()
        from cogs5e.initiative import Combat
        try:
            combat = await Combat.from_ctx(inter)
            if not combat:
                return await inter.followup.send("No active combat found.", ephemeral=True)
        except Exception as e:
            return await inter.followup.send("No active combat found.", ephemeral=True)
            
        if combat.dm_id != inter.author.id and not inter.permissions.manage_messages:
            return await inter.followup.send("You are not the DM of this combat.", ephemeral=True)
            
        # Import the madd function from initiative cog
        init_cog = self.bot.get_cog("InitTracker")
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
                
            async def trigger_typing(self):
                pass
                
            @property
            def clean_prefix(self):
                return "/"
                
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




    @slash_init.sub_command(name="remove", description="Removes a combatant from initiative.")
    async def init_remove(
        self,
        inter: disnake.ApplicationCommandInteraction,
        target: str = commands.Param(description="The name of the combatant to remove")
    ):
        await inter.response.defer()
        from cogs5e.initiative import Combat
        try:
            combat = await Combat.from_ctx(inter)
            if not combat:
                return await inter.followup.send("No active combat found.", ephemeral=True)
        except Exception:
            return await inter.followup.send("No active combat found.", ephemeral=True)
            
        if combat.dm_id != inter.author.id and not inter.permissions.manage_messages:
            return await inter.followup.send("You are not the DM of this combat.", ephemeral=True)
            
        init_cog = self.bot.get_cog("InitTracker")
        if not init_cog: return await inter.followup.send("Module not loaded", ephemeral=True)
        
        class FakeCtx:
            def __init__(self, inter):
                self.author = inter.author; self.channel = inter.channel; self.guild = inter.guild; self.bot = inter.bot
            async def send(self, *args, **kwargs): pass
            async def trigger_typing(self): pass
            @property
            def clean_prefix(self): return "/"
        
        fake_ctx = FakeCtx(inter)
        try:
            await init_cog.remove_combatant(fake_ctx, name=target)
            from cogs5e.initiative.utils import send_turn_message
            await send_turn_message(fake_ctx, combat)
            await inter.followup.send(f"Removed {target} from combat.", ephemeral=True)
        except Exception as e:
            await inter.followup.send(f"Error: {str(e)}", ephemeral=True)

    @init_remove.autocomplete("target")
    async def init_remove_combatant_target_auto(self, inter: disnake.ApplicationCommandInteraction, user_input: str):
        from cogs5e.initiative import Combat
        try:
            combat = await Combat.from_ctx(inter)
            if not combat: return []
            choices = [c.name for c in combat.combatants if user_input.lower() in c.name.lower()][:25]
            return choices
        except: return []

    @slash_init.sub_command(name="effect", description="Adds an effect to a specific combatant.")
    async def init_effect(
        self,
        inter: disnake.ApplicationCommandInteraction,
        target: str = commands.Param(description="The combatant to apply the effect to"),
        effect: str = commands.Param(description="The effect to apply (e.g. 'Stunned')"),
        duration: int = commands.Param(description="Duration in rounds", default=None),
        concentration: bool = commands.Param(description="Does this require concentration?", default=False),
        end_of_turn: bool = commands.Param(description="Tick duration at the END of turn instead of start?", default=False)
    ):
        await inter.response.defer()
        from cogs5e.initiative import Combat
        try:
            combat = await Combat.from_ctx(inter)
            if not combat: return await inter.followup.send("No active combat.", ephemeral=True)
        except Exception: return await inter.followup.send("No active combat.", ephemeral=True)
        
        init_cog = self.bot.get_cog("InitTracker")
        class FakeCtx:
            def __init__(self, inter):
                self.author = inter.author; self.channel = inter.channel; self.guild = inter.guild; self.bot = inter.bot
            async def send(self, *args, **kwargs): pass
            async def trigger_typing(self): pass
            @property
            def clean_prefix(self): return "/"
            async def get_combat(self): return combat
            
        fake_ctx = FakeCtx(inter)
        try:
            args_str = ""
            if duration is not None:
                args_str += f" -dur {duration}"
            if concentration:
                args_str += " conc"
            if end_of_turn:
                args_str += " end"
            await init_cog.effect(fake_ctx, target, effect, args=args_str)
            from cogs5e.initiative.utils import send_turn_message
            await send_turn_message(fake_ctx, combat)
            await inter.followup.send(f"Added effect '{effect}' to {target}.", ephemeral=True)
        except Exception as e:
            await inter.followup.send(f"Error: {str(e)}", ephemeral=True)

    @init_effect.autocomplete("target")
    async def init_effect_target_auto(self, inter, user_input: str):
        return await self.init_remove_target_auto(inter, user_input)

    @init_effect.autocomplete("effect")
    async def init_effect_name_auto(self, inter: disnake.ApplicationCommandInteraction, user_input: str):
        conditions = [
            "Blinded", "Charmed", "Deafened", "Exhaustion", "Frightened", 
            "Grappled", "Incapacitated", "Invisible", "Paralyzed", 
            "Petrified", "Poisoned", "Prone", "Restrained", 
            "Stunned", "Unconscious", "Concentrating"
        ]
        return [c for c in conditions if user_input.lower() in c.lower()][:25]

    @slash_init.sub_command(name="name", description="Change the name of a combatant.")
    async def init_name(
        self,
        inter: disnake.ApplicationCommandInteraction,
        target: str = commands.Param(description="The current name of the combatant"),
        name: str = commands.Param(description="The new name for the combatant")
    ):
        await inter.response.defer()
        from cogs5e.initiative import Combat
        try:
            combat = await Combat.from_ctx(inter)
            if not combat: return await inter.followup.send("No active combat.", ephemeral=True)
        except Exception: return await inter.followup.send("No active combat.", ephemeral=True)
        
        if combat.dm_id != inter.author.id and not inter.permissions.manage_messages:
            return await inter.followup.send("You are not the DM of this combat.", ephemeral=True)
            
        init_cog = self.bot.get_cog("InitTracker")
        class FakeCtx:
            def __init__(self, inter):
                self.author = inter.author; self.channel = inter.channel; self.guild = inter.guild; self.bot = inter.bot
            async def send(self, *args, **kwargs): pass
            async def trigger_typing(self): pass
            @property
            def clean_prefix(self): return "/"
            async def get_combat(self): return combat
            
        fake_ctx = FakeCtx(inter)
        try:
            await init_cog.opt(fake_ctx, target, args=f'-name "{name}"')
            from cogs5e.initiative.utils import send_turn_message
            await send_turn_message(fake_ctx, combat)
            await inter.followup.send(f"Changed {target}'s name to {name}.", ephemeral=True)
        except Exception as e:
            await inter.followup.send(f"Error: {str(e)}", ephemeral=True)

    @init_name.autocomplete("target")
    async def init_name_target_auto(self, inter, user_input: str):
        return await self.init_remove_target_auto(inter, user_input)

    @slash_init.sub_command(name="position", description="Changes a combatant's position in the initiative order.")
    async def init_position(
        self,
        inter: disnake.ApplicationCommandInteraction,
        target: str = commands.Param(description="The combatant to move"),
        position: str = commands.Param(description="The new initiative number (or +/- value)")
    ):
        await inter.response.defer()
        from cogs5e.initiative import Combat
        try:
            combat = await Combat.from_ctx(inter)
            if not combat: return await inter.followup.send("No active combat.", ephemeral=True)
        except Exception: return await inter.followup.send("No active combat.", ephemeral=True)
        
        if combat.dm_id != inter.author.id and not inter.permissions.manage_messages:
            return await inter.followup.send("You are not the DM of this combat.", ephemeral=True)
            
        init_cog = self.bot.get_cog("InitTracker")
        class FakeCtx:
            def __init__(self, inter):
                self.author = inter.author; self.channel = inter.channel; self.guild = inter.guild; self.bot = inter.bot
            async def send(self, *args, **kwargs): pass
            async def trigger_typing(self): pass
            @property
            def clean_prefix(self): return "/"
            async def get_combat(self): return combat
            
        fake_ctx = FakeCtx(inter)
        try:
            await init_cog.opt(fake_ctx, target, args=f'-p {position}')
            from cogs5e.initiative.utils import send_turn_message
            await send_turn_message(fake_ctx, combat)
            await inter.followup.send(f"Moved {target} to position {position}.", ephemeral=True)
        except Exception as e:
            await inter.followup.send(f"Error: {str(e)}", ephemeral=True)

    @init_position.autocomplete("target")
    async def init_position_target_auto(self, inter, user_input: str):
        return await self.init_remove_target_auto(inter, user_input)


def setup(bot):
    bot.add_cog(InitSlashCog(bot))
