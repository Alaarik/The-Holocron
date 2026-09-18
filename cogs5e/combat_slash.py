import disnake
from disnake.ext import commands
from cogs5e.ui.combat_gui import CombatView

class CombatSlashCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.slash_command(name="attack", description="Make an attack roll.")
    async def slash_attack(
        self, 
        inter: disnake.ApplicationCommandInteraction,
        weapon: str = commands.Param(description="The weapon or attack to use."),
        target: str = commands.Param(description="The target of the attack.", default="")
    ):
        from cogs5e.models.character import Character
        try:
            character = await Character.from_ctx(inter, use_global=True, use_guild=True, use_channel=True)
        except Exception:
            character = None
            
        if not character:
            return await inter.response.send_message("You do not have an active character.", ephemeral=True)
            
        atk = character.get_attack(weapon)
        if not atk:
            return await inter.response.send_message(f"Attack '{weapon}' not found on your sheet.", ephemeral=True)

        view = CombatView(inter, weapon, target, character)
        if len(view.valid_modifiers) > 0:
            await inter.response.send_message("Select any modifiers for your attack, then click Roll:", view=view, ephemeral=True)
        else:
            await view.confirm_roll(None, inter)

    @slash_attack.autocomplete("weapon")
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
        
    @slash_attack.autocomplete("target")
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

def setup(bot):
    bot.add_cog(CombatSlashCog(bot))
