import asyncio
from cogs5e.sheets.sw5e import SW5ESheetParser

async def test():
    with open("scratch/character.json") as f:
        json_data = f.read()
    parser = SW5ESheetParser(json_data=json_data)
    char = await parser.get_character()
    print("Name:", char.name)
    print("Level:", char.levels)
    print("HP:", char.hp, "/", char.max_hp)
    print("Stats:", [f"{k}={v.value}" for k, v in char.stats])

asyncio.run(test())
