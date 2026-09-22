import disnake
from disnake.ext import commands
from cogs5e.ui.combat_gui import CombatView

class CombatSlashCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(name="action", description="Take an action, bonus action, or attack.")
    async def slash_action(
        self, 
        inter: disnake.ApplicationCommandInteraction,
        action: str = commands.Param(description="The action, feature, or weapon to use."),
        target: str = commands.Param(description="The target of the attack.", default="")
    ):
        from cogs5e.models.character import Character
        try:
            character = await Character.from_ctx(inter, use_global=True, use_guild=True, use_channel=True)
        except Exception:
            character = None
            
        if not character:
            return await inter.followup.send("You do not have an active character.")
            
        atk = character.get_attack(action)
        if not atk:
            return await inter.response.send_message(f"Action '{action}' not found on your sheet.")

        view = CombatView(inter, action, target, character)
        if len(view.valid_modifiers) > 0:
            await inter.response.send_message("Select any modifiers for your attack, then click Roll:", view=view)
        else:
            await view.confirm_roll(None, inter)

    @slash_action.autocomplete("action")
    async def attack_weapon_auto(self, inter: disnake.ApplicationCommandInteraction, user_input: str):
        from cogs5e.models.character import Character
        try:
            character = await Character.from_ctx(inter, use_global=True, use_guild=True, use_channel=True)
        except Exception:
            return []
            
        choices = []
        pools = [character.attacks]
        if hasattr(character, "actions") and character.actions:
            pools.append(character.actions)
            
        for pool in pools:
            for atk in pool:
                if atk.name not in ["Sneak Attack", "Force-Empowered Strikes", "Ranger's Quarry", "Kinetic Combat", "Superiority Die", "Potent Aptitude"]:
                    if user_input.lower() in atk.name.lower():
                        if atk.name not in choices:
                            choices.append(atk.name)
        return choices[:25]
        
    @slash_action.autocomplete("target")
    async def attack_target_auto(self, inter: disnake.ApplicationCommandInteraction, user_input: str):
        from cogs5e.initiative import Combat
        try:
            combat = await Combat.from_ctx(inter)
            if not combat:
                return []
        except Exception:
            return []
            
        choices = []
        for c in combat.combatants:
            if user_input.lower() in c.name.lower():
                choices.append(c.name)
        return choices[:25]

    @commands.slash_command(name="power", description="Cast a Force or Tech power.")
    async def slash_cast(
        self, 
        inter: disnake.ApplicationCommandInteraction,
        power: str = commands.Param(description="The power to cast."),
        level: int = commands.Param(description="The level to cast the power at (defaults to base level).", default=None),
        target: str = commands.Param(description="The target of the power.", default="")
    ):
        await inter.response.defer()
        from cogs5e.models.character import Character
        try:
            character = await Character.from_ctx(inter, use_global=True, use_guild=True, use_channel=True)
        except Exception:
            character = None
            
        if not character:
            return await inter.followup.send("You do not have an active character.")
            
        from gamedata.compendium import compendium
        from utils.functions import search
        
        result, strict = search(compendium.spells, power, lambda s: s.name, strict=True)
        if not result:
            return await inter.followup.send(f"Power '{power}' not found in the compendium.")
            
        spell = result
        
        from cogs5e.utils.actionutils import cast_spell
        from cogs5e.utils.targetutils import maybe_combat
        from utils.argparser import argparse
        import traceback
        
        args_str = ""
        if target:
            args_str += f"-t \"{target}\" "
        if level is not None:
            args_str += f"-l {level} "
            
        args = argparse(args_str)
        embed = disnake.Embed()
        
        try:
            caster, targets, combat = await maybe_combat(inter, character, args)
            res = await cast_spell(
                spell=spell,
                ctx=inter,
                caster=caster,
                targets=targets,
                args=args,
                combat=combat
            )
            
            if res.embed:
                await inter.followup.send(embed=res.embed)
            else:
                await inter.followup.send("Power cast successfully.")
        except Exception as e:
            await inter.followup.send(f"Error casting power: {e}\n```\n{traceback.format_exc()}\n```")

    @slash_cast.autocomplete("power")
    async def cast_power_auto(self, inter: disnake.ApplicationCommandInteraction, user_input: str):
        from cogs5e.models.character import Character
        try:
            character = await Character.from_ctx(inter, use_global=True, use_guild=True, use_channel=True)
        except Exception:
            return []
            
        choices = []
        if hasattr(character, "spellbook") and character.spellbook:
            for s in character.spellbook.spells:
                if user_input.lower() in s.name.lower():
                    if s.name not in choices:
                        choices.append(s.name)
        return choices[:25]
        
    @slash_cast.autocomplete("target")
    async def cast_target_auto(self, inter: disnake.ApplicationCommandInteraction, user_input: str):
        from cogs5e.initiative import Combat
        try:
            combat = await Combat.from_ctx(inter)
            if not combat:
                return []
        except Exception:
            return []
            
        choices = []
        for c in combat.combatants:
            if user_input.lower() in c.name.lower():
                choices.append(c.name)
        return choices[:25]

def setup(bot):
    bot.add_cog(CombatSlashCog(bot))
