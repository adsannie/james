import os
import discord
import openai
import json
from dotenv import load_dotenv
from datetime import datetime
from zoneinfo import ZoneInfo


load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ASSISTANT_ID = os.getenv("OPENAI_ASSISTANT_ID")
CANAL_AUTORIZADO_ID = int(os.getenv("CANAL_AUTORIZADO_ID", "0"))
THREAD_MAP_FILE = "/data/thread_map.json"

openai.api_key = OPENAI_API_KEY

intents = discord.Intents.default()
intents.message_content = True
intents.messages = True
intents.guilds = True
intents.members = True
intents.guild_messages = True
client = discord.Client(intents=intents)

# Carregar mapeamento salvo do disco
def load_thread_map():
    try:
        with open(THREAD_MAP_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

# Salvar mapeamento no disco
def save_thread_map(data):
    with open(THREAD_MAP_FILE, "w") as f:
        json.dump(data, f)

thread_map = load_thread_map()

@client.event
async def on_ready():
    pass

@client.event
async def on_message(message):
    if message.author.bot:
        return

    if message.channel.id != CANAL_AUTORIZADO_ID and not isinstance(message.channel, discord.Thread):
        return

    if isinstance(message.channel, discord.Thread):
        discord_thread_id = str(message.channel.id)

        try:
            if discord_thread_id not in thread_map:
                openai_thread = openai.beta.threads.create()
                thread_map[discord_thread_id] = openai_thread.id
                save_thread_map(thread_map)
                await message.channel.send("🧠 Pronto! Podemos continuar nossa conversa por aqui. Fique à vontade para perguntar.")

            openai_thread_id = thread_map[discord_thread_id]

            await message.channel.send("⏳ Processando sua pergunta...")

            openai.beta.threads.messages.create(
                thread_id=openai_thread_id,
                role="user",
                content=message.content
            )

            run = openai.beta.threads.runs.create(
                thread_id=openai_thread_id,
                assistant_id=ASSISTANT_ID
            )

            while True:
                run_status = openai.beta.threads.runs.retrieve(
                    thread_id=openai_thread_id,
                    run_id=run.id
                )
                if run_status.status == "completed":
                    break

            messages = openai.beta.threads.messages.list(thread_id=openai_thread_id)
            resposta = messages.data[0].content[0].text.value

            await message.channel.send(resposta)

        except Exception:
            await message.channel.send("⚠️ O servidor está ocupado no momento. Tente novamente em instantes.")
        return

    try:
        agora = datetime.now(ZoneInfo("America/Sao_Paulo")).strftime("%d/%m %H:%M")

        nome_topico = f"Usuário: {message.author.display_name} • {agora}"

        thread = await message.channel.create_thread(
            name=nome_topico,
            type=discord.ChannelType.private_thread,
            invitable=False
        )
        await thread.add_user(message.author)
        await message.reply("✅ Criei um tópico privado para você. Vamos conversar por lá 👉")
        await thread.send("Pode mandar sua pergunta por aqui 😊")
    except Exception:
        await message.channel.send("⚠️ O servidor está ocupado no momento. Por favor, tente novamente.")

client.run(DISCORD_TOKEN)
