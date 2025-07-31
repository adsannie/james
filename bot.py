import os
import sys
import discord
import openai
import json
from dotenv import load_dotenv
from datetime import datetime
from zoneinfo import ZoneInfo

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
CANAL_AUTORIZADO_ID = int(os.getenv("CANAL_AUTORIZADO_ID", "0"))
HISTORICO_FILE = "/data/conversas.json"
TOPICOS_FILE = "/data/topicos.json"

openai.api_key = OPENAI_API_KEY

intents = discord.Intents.default()
intents.message_content = True
intents.messages = True
intents.guilds = True
intents.members = True
intents.guild_messages = True
client = discord.Client(intents=intents)

def load_json(path):
    try:
        with open(path, "r") as f:
            print(f"[DEBUG] {path} carregado.", file=sys.stderr, flush=True)
            return json.load(f)
    except FileNotFoundError:
        print(f"[DEBUG] {path} não encontrado. Criando novo.", file=sys.stderr, flush=True)
        return {}

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f)
    print(f"[DEBUG] {path} salvo.", file=sys.stderr, flush=True)

historico = load_json(HISTORICO_FILE)
topicos = load_json(TOPICOS_FILE)

@client.event
async def on_ready():
    print("✅ Bot iniciado com Responses API.", file=sys.stderr, flush=True)

@client.event
async def on_message(message):
    # print(f"[DEBUG] Mensagem recebida: {message.author}: {message.content}", file=sys.stderr, flush=True)

    if message.author.bot:
        return

    if message.channel.id != CANAL_AUTORIZADO_ID and not isinstance(message.channel, discord.Thread):
        return

    user_id = str(message.author.id)

    if isinstance(message.channel, discord.Thread):
        try:
            if user_id not in historico:
                historico[user_id] = []
            historico[user_id].append({"role": "user", "content": message.content})
            await message.channel.send("⏳ Processando sua pergunta...")

            response = openai.chat.completions.create(
                model="gpt-4o",
                messages=historico[user_id],
                temperature=0.7
            )
            resposta = response.choices[0].message.content
            historico[user_id].append({"role": "assistant", "content": resposta})

            await message.channel.send(resposta)
            save_json(HISTORICO_FILE, historico)

        except Exception as e:
            print(f"[ERRO]: {type(e).__name__} - {e}", file=sys.stderr, flush=True)
            await message.channel.send("⚠️ O servidor está ocupado no momento. Tente novamente em instantes.")
        return

    # Checar se já existe um tópico para esse usuário
    try:
        if user_id in topicos:
            # Verifica se o tópico ainda existe (pode ter sido apagado manualmente)
            try:
                thread = await client.fetch_channel(topicos[user_id])
                if isinstance(thread, discord.Thread):
                    await message.reply(
                        "👋 Você já tem um tópico privado!\n"
                        "Vamos continuar a conversa por lá:\n"
                        f"<#{thread.id}>"
                    )
                    await thread.send(f"{message.author.mention} está de volta ao tópico!")
                    return
            except Exception as e:
                print(f"[ERRO ao buscar thread]: {type(e).__name__} - {e}", file=sys.stderr, flush=True)
                # Se não encontrar o tópico, segue para criar um novo

        agora = datetime.now(ZoneInfo("America/Sao_Paulo")).strftime("%d/%m %H:%M")
        nome_topico = f"Usuário: {message.author.display_name} • {agora}"
        thread = await message.channel.create_thread(
            name=nome_topico,
            type=discord.ChannelType.private_thread,
            invitable=False
        )
        await thread.add_user(message.author)
        await message.reply(
            "✅ Criei um tópico privado para você!\n"
            "Vamos conversar por lá:\n"
            f"<#{thread.id}>"
        )
        await thread.send("Pode mandar sua pergunta por aqui 😊")
        topicos[user_id] = thread.id
        save_json(TOPICOS_FILE, topicos)

    except Exception as e:
        print(f"[ERRO AO CRIAR THREAD]: {type(e).__name__} - {e}", file=sys.stderr, flush=True)
        await message.channel.send("⚠️ O servidor está ocupado no momento. Por favor, tente novamente.")

client.run(DISCORD_TOKEN)
