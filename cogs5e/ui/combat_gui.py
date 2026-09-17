import disnake
from utils.argparser import argparse

class CombatView(disnake.ui.View):
    def __init__(self, inter, weapon, target, character):
        super().__init__(timeout=180)
        self.inter = inter
        self.weapon = weapon
        self.target = target
        self.character = character
        
        # Determine available modifiers
        self.valid_modifiers = []
        for atk in self.character.attacks:
            if atk.name in ["Sneak Attack", "Force-Empowered Strikes", "Ranger's Quarry", "Kinetic Combat", "Superiority Die", "Potent Aptitude"]:
                self.valid_modifiers.append(atk.name)
                
        if self.valid_modifiers:
            self.add_item(ModifierSelect(self.valid_modifiers))

    @disnake.ui.button(label="Roll Attack", style=disnake.ButtonStyle.primary)
    async def confirm_roll(self, button: disnake.ui.Button, interaction: disnake.MessageInteraction):
        if not interaction.response.is_done():
            await interaction.response.defer()
            
        args_str = ""
        if self.target:
            args_str += f"-t \"{self.target}\" "
            
        selected_mods = []
        for item in self.children:
            if isinstance(item, ModifierSelect):
                selected_mods = item.values
                break
                
        for mod_name in selected_mods:
            mod_atk = self.character.get_attack(mod_name)
            if mod_atk:
                if mod_name == "Sneak Attack":
                    import math
                    operative_levels = 0
                    for c in self.character.levels:
                        if c[0] == "Operative": operative_levels = c[1]
                    args_str += f"-d \"{math.ceil(operative_levels/2)}d6\" "
                elif mod_name == "Force-Empowered Strikes":
                    args_str += f"-d \"1d8\" " 
                elif mod_name == "Ranger's Quarry":
                    scout_levels = 0
                    for c in self.character.levels:
                        if c[0] == "Scout": scout_levels = c[1]
                    die = 4 if scout_levels < 5 else 6 if scout_levels < 9 else 8 if scout_levels < 13 else 10 if scout_levels < 17 else 12
                    args_str += f"-d \"1d{die}\" "
                    
        from cogs5e.utils.actionutils import run_attack
        from cogs5e.utils.targetutils import maybe_combat
        
        args = argparse(args_str)
        atk = self.character.get_attack(self.weapon)
        embed = disnake.Embed()
        
        caster, targets, combat = await maybe_combat(self.inter, self.character, args)
            
        await run_attack(
            ctx=self.inter,
            embed=embed,
            args=args,
            caster=caster,
            attack=atk,
            targets=targets,
            combat=combat
        )
        
        await interaction.followup.send(embed=embed)


class ModifierSelect(disnake.ui.StringSelect):
    def __init__(self, valid_modifiers):
        options = [
            disnake.SelectOption(label=mod, description=f"Add {mod} to this attack") 
            for mod in valid_modifiers
        ]
        super().__init__(
            placeholder="Select Attack Modifiers...",
            min_values=0,
            max_values=len(valid_modifiers),
            options=options,
        )

    async def callback(self, interaction: disnake.MessageInteraction):
        await interaction.response.defer()
