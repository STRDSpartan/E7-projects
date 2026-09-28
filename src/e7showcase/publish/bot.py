"""Bot Discord optionnel : `/vitrine` et `/draft` pour la guilde.

Chaque membre dépose son roster exporté (`e7showcase export`) via `/roster-upload`;
le bot stocke les rosters par membre et génère vitrines et vues de draft à la demande.
Squelette à compléter — voir la skill `discord-integration`.
"""

from __future__ import annotations

import io
import tempfile
from pathlib import Path

from e7showcase.config import data_dir, settings
from e7showcase.models.roster import Roster
from e7showcase.render.showcase import render_showcase
from e7showcase.storage.repository import RosterRepository


def _guild_repo(member_id: int) -> RosterRepository:
    return RosterRepository(data_dir() / "guild" / f"{member_id}.json")


def run() -> None:
    import discord
    from discord import app_commands

    intents = discord.Intents.default()
    client = discord.Client(intents=intents)
    tree = app_commands.CommandTree(client)

    @tree.command(name="roster-upload", description="Déposer son roster (fichier JSON exporté)")
    async def roster_upload(interaction: discord.Interaction, fichier: discord.Attachment) -> None:
        roster = Roster.model_validate_json(await fichier.read())
        _guild_repo(interaction.user.id).save(roster)
        await interaction.response.send_message(
            f"Roster enregistré : {len(roster.heroes)} héros.", ephemeral=True
        )

    @tree.command(
        name="vitrine", description="Afficher la vitrine d'un membre (ou un héros précis)"
    )
    async def vitrine(
        interaction: discord.Interaction,
        membre: discord.Member | None = None,
        heros: str | None = None,
    ) -> None:
        await interaction.response.defer()
        target = membre or interaction.user
        roster = _guild_repo(target.id).load()
        selection = [h] if heros and (h := roster.find(heros)) else None
        with tempfile.TemporaryDirectory() as tmp:
            images = render_showcase(
                roster, Path(tmp), selection, layout="cards" if selection else "grid"
            )
            files = [discord.File(io.BytesIO(p.read_bytes()), filename=p.name) for p in images[:10]]
        await interaction.followup.send(f"Vitrine de **{roster.player}**", files=files)

    @tree.command(name="draft", description="Qui possède ce héros dans la guilde ?")
    async def draft(interaction: discord.Interaction, heros: str) -> None:
        lines = []
        for f in sorted((data_dir() / "guild").glob("*.json")):
            roster = RosterRepository(f).load()
            if h := roster.find(heros):
                lines.append(
                    f"• **{roster.player}** — {h.name} · VIT {h.stats.spd} · "
                    f"{' / '.join(h.sets) or 'sans set'}"
                )
        await interaction.response.send_message("\n".join(lines) or "Personne ne possède ce héros.")

    @client.event
    async def on_ready() -> None:
        await tree.sync()

    client.run(settings()["discord"]["bot_token"])
