import discord
from discord.ext import commands
from discord import app_commands
import requests
import os
import json
import time
from datetime import timedelta
import redis as redislib

TOKEN = os.getenv("TOKEN")
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
REDIS_URL = os.getenv("REDIS_URL")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

ARCHIVO_PROPUESTAS = "propuestas.json"
REDIS_KEY = "propuestas"

redis_client = redislib.from_url(REDIS_URL) if REDIS_URL else None


def cargar_propuestas():
    if redis_client:
        try:
            data = redis_client.get(REDIS_KEY)
            if data:
                return json.loads(data)
            return []
        except Exception as e:
            print(f"Error cargando desde Redis: {e}")
    try:
        with open(ARCHIVO_PROPUESTAS, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []


def guardar_propuestas():
    if redis_client:
        try:
            redis_client.set(REDIS_KEY, json.dumps(lista_propuestas, ensure_ascii=False))
            return
        except Exception as e:
            print(f"Error guardando en Redis: {e}")
    with open(ARCHIVO_PROPUESTAS, "w", encoding="utf-8") as f:
        json.dump(lista_propuestas, f, ensure_ascii=False, indent=2)


lista_propuestas = cargar_propuestas()


async def autocomplete_peliculas(interaction: discord.Interaction, current: str):

    if not current:
        return []

    url = "https://api.themoviedb.org/3/search/movie"

    params = {
        "api_key": TMDB_API_KEY,
        "query": current,
        "language": "es-ES"
    }

    response = requests.get(url, params=params)
    data = response.json()

    choices = []

    for movie in data["results"][:8]:

        titulo = movie["title"]
        anio = movie["release_date"][:4] if movie["release_date"] else "?"

        choices.append(
            app_commands.Choice(
                name=f"{titulo} ({anio})",
                value=titulo
            )
        )

    return choices


@bot.event
async def on_ready():
    await tree.sync()
    print("Bot conectado como " + str(bot.user))


@bot.command()
async def ping(ctx):
    await ctx.send("🎬 Club Semanal está funcionando!")


async def enviar_pelicula(channel, nombre):

    url = "https://api.themoviedb.org/3/search/movie"

    params = {
        "api_key": TMDB_API_KEY,
        "query": nombre,
        "language": "es-ES"
    }

    response = requests.get(url, params=params)
    data = response.json()

    if len(data["results"]) == 0:
        await channel.send("No encontré esa película 😢")
        return

    movie = data["results"][0]
    movie_id = movie["id"]

    titulo = movie["title"]
    titulo_original = movie["original_title"]

    if titulo != titulo_original:
        titulo_mostrar = f"{titulo} ({titulo_original})"
    else:
        titulo_mostrar = titulo

    descripcion = movie["overview"]
    rating = movie["vote_average"]
    fecha = movie["release_date"][:4] if movie["release_date"] else "?"

    poster_path = movie["poster_path"]
    poster_url = "https://image.tmdb.org/t/p/w500" + poster_path if poster_path else None

    proveedores_url = f"https://api.themoviedb.org/3/movie/{movie_id}/watch/providers"

    params_proveedores = {
        "api_key": TMDB_API_KEY
    }

    response_proveedores = requests.get(proveedores_url, params=params_proveedores)
    data_proveedores = response_proveedores.json()

    plataformas = []

    if "AR" in data_proveedores.get("results", {}):
        if "flatrate" in data_proveedores["results"]["AR"]:
            for p in data_proveedores["results"]["AR"]["flatrate"]:
                plataformas.append(p["provider_name"])

    if len(plataformas) == 0:
        plataformas_texto = "No disponible en streaming en Argentina"
    else:
        plataformas_texto = ", ".join(plataformas)

    query = f"{titulo} {fecha} trailer".replace(" ", "+")
    trailer_url = f"https://www.youtube.com/results?search_query={query}"

    embed = discord.Embed(
        title=f"🎬 {titulo_mostrar}",
        color=0x00ffcc
    )

    if poster_url:
        embed.set_image(url=poster_url)

    embed.add_field(name="📺 Dónde verla", value=plataformas_texto, inline=False)
    embed.add_field(name="📅 Año", value=fecha, inline=True)
    embed.add_field(name="⭐ Rating", value=rating, inline=True)
    embed.add_field(
        name="📝 Descripción",
        value=descripcion[:500] + "..." if descripcion and len(descripcion) > 500 else descripcion,
        inline=False
    )
    embed.add_field(name="▶ Trailer", value=trailer_url, inline=False)
    embed.add_field(name=" ", value="──────────", inline=False)

    await channel.send(embed=embed)


@tree.command(name="proponer", description="Proponer una película")
@app_commands.autocomplete(nombre=autocomplete_peliculas)
async def proponer(interaction: discord.Interaction, nombre: str):

    url = "https://api.themoviedb.org/3/search/movie"

    params = {
        "api_key": TMDB_API_KEY,
        "query": nombre,
        "language": "es-ES"
    }

    response = requests.get(url, params=params)
    data = response.json()

    if len(data["results"]) == 0:
        await interaction.response.send_message("No encontré esa película 😢", ephemeral=True)
        return

    movie = data["results"][0]

    titulo = movie["title"]
    titulo_original = movie["original_title"]

    if titulo != titulo_original:
        titulo_mostrar = f"{titulo} ({titulo_original})"
    else:
        titulo_mostrar = titulo

    for peli in lista_propuestas:
        if peli["titulo"].lower() == titulo_mostrar.lower():
            await interaction.response.send_message("⚠ Esa película ya fue propuesta.", ephemeral=True)
            return

    movie_id = movie["id"]
    proveedores_url = f"https://api.themoviedb.org/3/movie/{movie_id}/watch/providers"
    response_proveedores = requests.get(proveedores_url, params={"api_key": TMDB_API_KEY})
    data_proveedores = response_proveedores.json()

    plataformas = []
    if "AR" in data_proveedores.get("results", {}):
        if "flatrate" in data_proveedores["results"]["AR"]:
            for p in data_proveedores["results"]["AR"]["flatrate"]:
                plataformas.append(p["provider_name"])

    plataformas_texto = ", ".join(plataformas) if plataformas else "No disponible en streaming"

    lista_propuestas.append({
        "titulo": titulo_mostrar,
        "busqueda": nombre,
        "plataformas": plataformas_texto
    })

    guardar_propuestas()

    await interaction.response.send_message(
        f"🎬 **{titulo_mostrar}** fue agregada a las propuestas.",
        ephemeral=True
    )


class PublicarSelect(discord.ui.Select):

    def __init__(self):

        options = []

        propuestas_mostradas = lista_propuestas[:25]

        for i, peli in enumerate(propuestas_mostradas):
            options.append(
                discord.SelectOption(
                    label=peli["titulo"][:100],
                    value=str(i)
                )
            )

        super().__init__(
            placeholder="Elegí las películas para publicar",
            min_values=1,
            max_values=min(5, len(options)),
            options=options
        )

    async def callback(self, interaction: discord.Interaction):

        await interaction.response.defer(ephemeral=True)

        seleccionadas = []

        for index in self.values:
            seleccionadas.append(lista_propuestas[int(index)])

        titulos_encuesta = []

        await interaction.channel.send("🍿 **Películas de esta semana**")

        for peli in seleccionadas:
            titulos_encuesta.append(peli["titulo"])
            await enviar_pelicula(interaction.channel, peli["busqueda"])

        for peli in seleccionadas:
            lista_propuestas.remove(peli)

        guardar_propuestas()

        try:
            poll = discord.Poll(
                question="¿Cuál vemos esta semana?",
                duration=timedelta(hours=24)
            )
            for titulo in titulos_encuesta:
                poll.add_answer(text=titulo[:55])
            await interaction.channel.send(poll=poll)
            await interaction.followup.send("Películas publicadas ✅", ephemeral=True)
        except Exception as e:
            print(f"Error enviando encuesta: {e}")
            await interaction.followup.send(f"⚠ Películas publicadas pero no se pudo crear la encuesta: {e}", ephemeral=True)


class PublicarView(discord.ui.View):

    def __init__(self):
        super().__init__()
        self.add_item(PublicarSelect())


class EliminarSelect(discord.ui.Select):

    def __init__(self):

        options = []

        for i, peli in enumerate(lista_propuestas[:25]):
            options.append(
                discord.SelectOption(
                    label=peli["titulo"][:100],
                    value=str(i)
                )
            )

        super().__init__(
            placeholder="Elegí las películas a eliminar",
            min_values=1,
            max_values=len(options),
            options=options
        )

    async def callback(self, interaction: discord.Interaction):

        indices = sorted([int(v) for v in self.values], reverse=True)

        eliminadas = []

        for index in indices:
            eliminadas.append(lista_propuestas[index]["titulo"])
            lista_propuestas.pop(index)

        guardar_propuestas()

        titulos = "\n".join(f"- {t}" for t in eliminadas)
        await interaction.response.send_message(
            f"🗑 Propuestas eliminadas:\n{titulos}",
            ephemeral=True
        )


class EliminarView(discord.ui.View):

    def __init__(self):
        super().__init__()
        self.add_item(EliminarSelect())


@tree.command(name="eliminar", description="Eliminar propuestas sin publicar")
async def eliminar_slash(interaction: discord.Interaction):

    if len(lista_propuestas) == 0:
        await interaction.response.send_message("No hay propuestas para eliminar.", ephemeral=True)
        return

    view = EliminarView()

    await interaction.response.send_message(
        "Elegí las propuestas a eliminar:",
        view=view,
        ephemeral=True
    )


@tree.command(name="publicar", description="Publicar encuesta con películas propuestas")
async def publicar_slash(interaction: discord.Interaction):

    if len(lista_propuestas) == 0:
        await interaction.response.send_message("No hay propuestas para publicar.", ephemeral=True)
        return

    view = PublicarView()

    await interaction.response.send_message(
        "Elegí las películas para la encuesta:",
        view=view,
        ephemeral=True
    )


@bot.command()
async def propuestas(ctx):

    await ctx.message.delete()

    if len(lista_propuestas) == 0:
        await ctx.author.send("No hay propuestas todavía.")
        return

    encabezado = "🍿 **Películas propuestas**\n\n"
    lineas = []

    for i, peli in enumerate(lista_propuestas, start=1):
        plataforma = peli.get("plataformas", "desconocida")
        lineas.append(f"{i}. {peli['titulo']} — {plataforma}")

    mensaje = encabezado
    for linea in lineas:
        if len(mensaje) + len(linea) + 1 > 1900:
            await ctx.author.send(mensaje)
            mensaje = ""
        mensaje += linea + "\n"

    if mensaje:
        await ctx.author.send(mensaje)


@bot.command()
async def preview(ctx, *numeros):

    await ctx.message.delete()

    if len(numeros) == 0:
        await ctx.author.send("Tenés que indicar los números de las películas.")
        return

    seleccionadas = []

    for n in numeros:
        try:
            index = int(n) - 1
        except:
            continue

        if index < len(lista_propuestas):
            seleccionadas.append(lista_propuestas[index])

    if len(seleccionadas) == 0:
        await ctx.author.send("No encontré esas propuestas.")
        return

    await ctx.author.send("🎬 **Preview de publicación**")

    for peli in seleccionadas:
        await enviar_pelicula(ctx.author, peli["busqueda"])


time.sleep(5)

bot.run(TOKEN)
