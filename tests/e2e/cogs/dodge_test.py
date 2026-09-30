import disnake
import pytest
import re
from unittest.mock import AsyncMock, Mock

from tests.utils import (
    ContextBotProxy,
    active_character,
    active_combat,
    end_init,
    requires_data,
    start_init,
)
from utils.enums import AdvantageType

pytestmark = pytest.mark.asyncio


class DodgeInterProxy(ContextBotProxy):
    """Mimics a slash interaction backed by the real test bot and DB."""

    def __init__(self, bot):
        super().__init__(bot)
        self.response = Mock()
        self.response.defer = AsyncMock()
        self.followup = Mock()
        self.followup.send = AsyncMock()


def get_dodge_cog(avrae):
    cog = avrae.get_cog("InitSlashCog")
    assert cog is not None, "InitSlashCog is not loaded"
    return cog


async def get_attack_result_embed(dhttp):
    """Skips the attack announcement/summary requests, returns the result embed."""
    for _ in range(5):
        request = await dhttp.get_request()
        if request.method == "POST" and isinstance(request.data, dict) and "embeds" in request.data:
            return request.data["embeds"][0]
    raise AssertionError("never received the attack result embed")


@pytest.mark.usefixtures("init_fixture", "character")
class TestDodge:
    @requires_data()
    async def test_dodge_no_combat(self, avrae, dhttp):
        cog = get_dodge_cog(avrae)
        inter = DodgeInterProxy(avrae)
        await cog.slash_dodge(inter, "")
        inter.followup.send.assert_called_once_with("No active combat found.", ephemeral=True)

    async def test_dodge_setup(self, avrae, dhttp):
        await start_init(avrae, dhttp)
        avrae.message("!init join")
        await dhttp.drain()
        avrae.message("!init madd kobold")
        await dhttp.drain()
        avrae.message("!init next")
        await dhttp.drain()

    async def test_attack_normal(self, avrae, dhttp):
        character = await active_character(avrae)
        atk_name = character.attacks[0].name
        dhttp.clear()
        avrae.message(f'!i aoo "{character.name}" "{atk_name}" -t "KO1"')
        await dhttp.receive_delete()
        embed = await get_attack_result_embed(dhttp)
        assert re.match(rf".* attacks with a {re.escape(atk_name)}!", embed["title"])
        assert embed["fields"][0]["name"] == "KO1"
        assert "2d20" not in embed["fields"][0]["value"]

    async def test_dodge_default_target(self, avrae, dhttp):
        character = await active_character(avrae)
        cog = get_dodge_cog(avrae)
        inter = DodgeInterProxy(avrae)
        await cog.slash_dodge(inter, "")
        inter.followup.send.assert_called_once_with(f"{character.name} is Dodging until the start of their next turn.")
        combatant = (await active_combat(avrae)).get_combatant(character.name)
        effect = combatant.get_effect("Dodging")
        assert effect is not None
        assert effect.effects.save_adv == {"dex"}
        assert effect.effects.attack_advantage_against == AdvantageType.DIS
        assert effect.duration == 1
        assert effect.end_on_turn_end is False

    async def test_dodge_named_target(self, avrae, dhttp):
        cog = get_dodge_cog(avrae)
        inter = DodgeInterProxy(avrae)
        await cog.slash_dodge(inter, "KO1")
        inter.followup.send.assert_called_once_with("KO1 is Dodging until the start of their next turn.")
        combatant = (await active_combat(avrae)).get_combatant("KO1")
        effect = combatant.get_effect("Dodging")
        assert effect is not None
        assert effect.effects.save_adv == {"dex"}
        assert effect.effects.attack_advantage_against == AdvantageType.DIS

    async def test_dodge_duplicate(self, avrae, dhttp):
        character = await active_character(avrae)
        cog = get_dodge_cog(avrae)
        inter = DodgeInterProxy(avrae)
        await cog.slash_dodge(inter, "")
        inter.followup.send.assert_called_once_with(f"{character.name} is already Dodging.", ephemeral=True)

    async def test_dodge_attack_disadvantage(self, avrae, dhttp):
        character = await active_character(avrae)
        atk_name = character.attacks[0].name
        dhttp.clear()
        avrae.message(f'!i aoo "{character.name}" "{atk_name}" -t "KO1"')
        await dhttp.receive_delete()
        embed = await get_attack_result_embed(dhttp)
        assert re.match(rf".* attacks with a {re.escape(atk_name)}!", embed["title"])
        assert embed["fields"][0]["name"] == "KO1"
        assert "2d20kl1" in embed["fields"][0]["value"]

    async def test_dodge_dex_save_advantage(self, avrae, dhttp):
        character = await active_character(avrae)
        dhttp.clear()
        avrae.message(f'!i os "{character.name}" dex')
        await dhttp.receive_delete()
        save_embed = disnake.Embed(description=r"[\s\S]*2d20kh1[\s\S]*")
        await dhttp.receive_message(embed=save_embed)

    async def test_dodge_expires_next_turn(self, avrae, dhttp):
        character = await active_character(avrae)
        for _ in range(6):
            combatant = (await active_combat(avrae)).get_combatant(character.name)
            if combatant.get_effect("Dodging") is None:
                break
            avrae.message("!init next")
            await dhttp.drain()
        else:
            pytest.fail("Dodging did not expire at the start of the next turn")
        combatant = (await active_combat(avrae)).get_combatant(character.name)
        assert combatant.get_effect("Dodging") is None

    async def test_dodge_teardown(self, avrae, dhttp):
        await end_init(avrae, dhttp)
