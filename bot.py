import os
import sys
import discord
import openai
import json
import traceback
from dotenv import load_dotenv
from datetime import datetime
from zoneinfo import ZoneInfo

# Verificação do disco /data
DATA_PATH = "/data"
if not os.path.exists(DATA_PATH):
    print(f"[ERRO] O diretório {DATA_PATH} NÃO existe!", file=sys.stderr, flush=True)
else:
    print(f"[OK] O diretório {DATA_PATH} existe.", file=sys.stderr, flush=True)
    try:
        testfile = os.path.join(DATA_PATH, "test.tmp")
        with open(testfile, "w") as f:
            f.write("teste")
        os.remove(testfile)
        print(f"[OK] O diretório {DATA_PATH} é gravável.", file=sys.stderr, flush=True)
    except Exception as e:
        print(f"[ERRO] Não é possível gravar em {DATA_PATH}: {e}", file=sys.stderr, flush=True)

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_ASSISTANT_ID = os.getenv("OPENAI_ASSISTANT_ID")
CANAL_AUTORIZADO_ID = int(os.getenv("CANAL_AUTORIZADO_ID", "0"))
THREADS_FILE = "/data/assistant_threads.json"
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

def dividir_mensagem(texto, limite=2000):
    return [texto[i:i+limite] for i in range(0, len(texto), limite)]

assistant_threads = load_json(THREADS_FILE)
topicos = load_json(TOPICOS_FILE)

@client.event
async def on_ready():
    print("✅ Bot iniciado com Assistants API.", file=sys.stderr, flush=True)

@client.event
async def on_message(message):
    if message.author.bot:
        return

    if message.channel.id != CANAL_AUTORIZADO_ID and not isinstance(message.channel, discord.Thread):
        return

    user_id = str(message.author.id)

    if isinstance(message.channel, discord.Thread):
        try:
            print("[DEBUG] Entrou na thread do usuário.", file=sys.stderr, flush=True)

            # Mapeamento: ID do tópico Discord <-> Thread da OpenAI
            discord_thread_id = str(message.channel.id)

            if discord_thread_id not in assistant_threads:
                # Cria thread OpenAI para o usuário (um para cada tópico Discord)
                openai_thread = openai.beta.threads.create()
                assistant_threads[discord_thread_id] = openai_thread.id
                save_json(THREADS_FILE, assistant_threads)
                await message.channel.send("🧠 Pronto! Podemos continuar nossa conversa por aqui. Fique à vontade para perguntar.")

            openai_thread_id = assistant_threads[discord_thread_id]
            await message.channel.send("⏳ Processando sua pergunta...")

            # Adiciona mensagem do usuário
            openai.beta.threads.messages.create(
                thread_id=openai_thread_id,
                role="user",
                content=message.content
            )

            # Executa o assistant
            run = openai.beta.threads.runs.create(
                thread_id=openai_thread_id,
                assistant_id=OPENAI_ASSISTANT_ID
            )

            # Aguarda até completar
            while True:
                run_status = openai.beta.threads.runs.retrieve(
                    thread_id=openai_thread_id,
                    run_id=run.id
                )
                if run_status.status == "completed":
                    break

            messages = openai.beta.threads.messages.list(thread_id=openai_thread_id)
            resposta = messages.data[0].content[0].text.value

            # Envia resposta (em blocos de até 2000 caracteres)
            for parte in dividir_mensagem(resposta):
                await message.channel.send(parte)

            save_json(THREADS_FILE, assistant_threads)

        except Exception as e:
            print(f"[ERRO]: {type(e).__name__} - {e}", file=sys.stderr, flush=True)
            traceback.print_exc(file=sys.stderr)
            await message.channel.send("⚠️ O servidor está ocupado no momento. Tente novamente em instantes.")
        return

    # Checar se já existe um tópico para esse usuário
    try:
        if user_id in topicos:
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
        traceback.print_exc(file=sys.stderr)
        await message.channel.send("⚠️ O servidor está ocupado no momento. Por favor, tente novamente.")

client.run(DISCORD_TOKEN)
