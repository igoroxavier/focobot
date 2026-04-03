#Bibliotecas 
import discord
from discord.ext import commands
import os
import asyncio
import logging
import time
import json
from dotenv import load_dotenv

#Configuração do Logger 
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s » %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

#Constantes 
ARQUIVO_XP: str = "xp.json"
XP_POR_MINUTO: int = 10
XP_POR_NIVEL: int = 500
TOP_RANKING: int = 10

#Carrega o token da .env 
load_dotenv()
TOKEN: str | None = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    logger.critical("Token não encontrado! Verifique o arquivo .env.")
    raise ValueError("DISCORD_TOKEN não definido no arquivo .env")

#Configuração do bot 
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="focobot.", intents=intents)
bot.remove_command("help")

#Estado global 
sessoesAtivas: dict = {}
xpLock = asyncio.Lock()  # Protege operações de leitura/escrita no arquivo JSON


#Funções auxiliares de XP
def carregarXp() -> dict:
    """Carrega os dados de XP do arquivo JSON.
    Cria o arquivo com um dicionário vazio caso ele não exista.
    """
    if not os.path.exists(ARQUIVO_XP):
        logger.info("Arquivo '%s' não encontrado. Criando novo...", ARQUIVO_XP)
        with open(ARQUIVO_XP, "w") as f:
            json.dump({}, f)
        return {}

    with open(ARQUIVO_XP, "r") as f:
        return json.load(f)


def salvarXp(dados: dict) -> None:
    """Salva os dados de XP no arquivo JSON."""
    with open(ARQUIVO_XP, "w") as f:
        json.dump(dados, f, indent=4)


#Eventos do bot 
@bot.event
async def on_ready() -> None:
    """Executado quando o bot se conecta ao Discord com sucesso."""
    logger.info("Logado com sucesso como %s (ID: %s)", bot.user, bot.user.id)

    atividade = discord.Activity(
        type=discord.ActivityType.watching,
        name="Auxiliando no seu foco 🧠",
    )
    await bot.change_presence(status=discord.Status.online, activity=atividade)


@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError) -> None:
    """Tratamento global de erros para todos os comandos."""
    if isinstance(error, commands.CommandNotFound):
        await ctx.send(
            f"❓ Comando não encontrado, {ctx.author.mention}. "
            "Digite `focobot.ajuda` para ver os comandos disponíveis!"
        )
    elif isinstance(error, commands.BotMissingPermissions):
        await ctx.send(
            "❌ Não tenho permissão para fazer isso neste servidor! "
            "Verifique meus cargos."
        )
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(
            f"⚠️ {ctx.author.mention}, argumento faltando! "
            "Use `focobot.ajuda` para ver o uso correto do comando."
        )
    else:
        logger.error("Erro não tratado no comando '%s': %s", ctx.command, error)


#Comandos 
@bot.command()
async def ping(ctx: commands.Context) -> None:
    """Verifica se o bot está online e respondendo."""
    await ctx.send("🏓 Pong! O bot está online e funcionando.")


@bot.command()
async def foco(ctx: commands.Context, minutos: int = None) -> None:
    """Inicia uma sessão de foco para o usuário.

    Silencia o usuário na call de voz (se estiver em uma) e registra
    o XP ao término da sessão.
    """
    if minutos is None:
        await ctx.send(
            f"⚠️ {ctx.author.mention}, você não informou o tempo de foco! "
            "Use: `focobot.foco [minutos]`. Exemplo: `focobot.foco 25`"
        )
        return  # Encerra a execução para evitar erros abaixo

    usuario = ctx.author

    if usuario.id in sessoesAtivas:
        await ctx.send(
            f"{usuario.mention}, você já tem uma sessão de foco ativa! "
            "Cancele a atual com `focobot.cancelar` antes de iniciar outra."
        )
        return

    segundos = minutos * 60
    tempoFim = time.time() + segundos

    cancelaFoco = asyncio.Event()
    sessoesAtivas[usuario.id] = {
        "cancelar": cancelaFoco,
        "tempoRestante": tempoFim,
    }

    # Silencia o usuário caso esteja em canal de voz
    if usuario.voice and usuario.voice.channel:
        try:
            await usuario.edit(mute=True, deafen=True)
            await ctx.send(
                f"📖 {usuario.mention} entrou no modo foco por **{minutos} minutos**! Foco total."
            )
        except discord.errors.Forbidden:
            await ctx.send(
                f"❌ {usuario.mention}, não tenho permissão para te silenciar! "
                "Coloque meu cargo acima do seu nas configurações do servidor."
            )
            del sessoesAtivas[usuario.id]
            return
    else:
        await ctx.send(
            f"⏱️ {usuario.mention} iniciou um timer de **{minutos} minutos**! "
            "(Entre em um canal de voz se quiser ser silenciado automaticamente.)"
        )

    # Aguarda o timer ou o cancelamento
    try:
        await asyncio.wait_for(cancelaFoco.wait(), timeout=segundos)
        foiCancelado = True
    except asyncio.TimeoutError:
        foiCancelado = False

    # Limpa a sessão ativa
    sessoesAtivas.pop(usuario.id, None)

    # Desmuta o usuário se ainda estiver em call
    if usuario.voice and usuario.voice.channel:
        try:
            await usuario.edit(mute=False, deafen=False)
        except discord.errors.Forbidden:
            logger.warning("Não foi possível desmutar %s após a sessão.", usuario)

    if foiCancelado:
        await ctx.send(
            f"🛑 O foco de {usuario.mention} foi cancelado antes da hora. "
            "*(Nenhum XP ganho!)*"
        )
        return

    # Sessão concluída — concede XP com proteção contra race condition
    xpGanho = minutos * XP_POR_MINUTO

    async with xpLock:
        dadosXp = carregarXp()
        userId = str(usuario.id)
        guildId = str(ctx.guild.id) #Pegamos o ID do servidor

        if guildId not in dadosXp: #Se o id do server não existe no banco de dados, cria
            dadosXp[guildId] = {}

        # Adiciona o XP do usuário dentro do servidor específico
        dadosXp[guildId][userId] = dadosXp[guildId].get(userId, 0) + xpGanho
        salvarXp(dadosXp)
        xpTotal = dadosXp[guildId][userId]

    nivelAtual = xpTotal // XP_POR_NIVEL
    await ctx.send(
        f"⏰ O tempo de foco de {usuario.mention} acabou! Bom trabalho!\n"
        f"✨ Você ganhou **+{xpGanho} XP**! "
        f"(XP Total: {xpTotal} | Nível: {nivelAtual})"
    )


@foco.error
async def focoError(ctx: commands.Context, error: commands.CommandError) -> None:
    """Tratamento de erros específico para o comando foco."""
    if isinstance(error, commands.BadArgument):
        await ctx.send(
            f"❌ {ctx.author.mention}, você precisa digitar um número inteiro! "
            "Tente: `focobot.foco 25`"
        )


@bot.command()
async def cancelar(ctx: commands.Context) -> None:
    """Cancela a sessão de foco ativa do usuário."""
    usuario = ctx.author
    if usuario.id in sessoesAtivas:
        sessoesAtivas[usuario.id]["cancelar"].set()
        await ctx.send(f"🔄 Cancelando o foco de {usuario.mention}...")
    else:
        await ctx.send(
            f"🤔 {usuario.mention}, você não tem nenhum foco ativo no momento!"
        )


@bot.command()
async def status(ctx: commands.Context) -> None:
    """Mostra o tempo restante da sessão de foco do usuário."""
    usuario = ctx.author

    if usuario.id not in sessoesAtivas:
        await ctx.send(
            f"🤔 {usuario.mention}, você não está em foco no momento. "
            "Use `focobot.foco` para começar!"
        )
        return

    tempoRestante = int(sessoesAtivas[usuario.id]["tempoRestante"] - time.time())
    minutosRestantes = tempoRestante // 60
    segundosRestantes = tempoRestante % 60

    await ctx.send(
        f"⏳ {usuario.mention}, faltam **{minutosRestantes}m e {segundosRestantes}s** "
        "para o seu foco acabar!"
    )


@bot.command()
async def statusall(ctx: commands.Context) -> None:
    """Lista o tempo restante de todas as sessões de foco ativas no servidor."""
    if not sessoesAtivas:
        await ctx.send("Ninguém está em foco no momento. Seja o primeiro!")
        return

    agora = time.time()
    mensagem = "**📊 Status do Foco Atual:**\n\n"

    for userId, dados in sessoesAtivas.items():
        membro = ctx.guild.get_member(userId)
        nome = membro.display_name if membro else "Usuário desconhecido"

        tempoRestante = int(dados["tempoRestante"] - agora)
        minutosRestantes = tempoRestante // 60
        segundosRestantes = tempoRestante % 60

        mensagem += f"🧠 **{nome}**: {minutosRestantes}m e {segundosRestantes}s restantes.\n"

    await ctx.send(mensagem)


@bot.command()
async def perfil(ctx: commands.Context) -> None:
    """Exibe o perfil de XP e nível do usuário em um embed."""
    dadosXp = carregarXp()
    userId = str(ctx.author.id)
    guildId = str(ctx.guild.id) #ID do servidor

    # Pega os dados do servidor. Se não existir, retorna um dicionário vazio {}
    dadosServidor = dadosXp.get(guildId, {})
    
    # Pega o XP do usuário dentro desse servidor
    xpTotal = dadosServidor.get(userId, 0)
    
    nivel = xpTotal // XP_POR_NIVEL
    xpProxNivel = XP_POR_NIVEL - (xpTotal % XP_POR_NIVEL)

    embed = discord.Embed(
        title=f"🏆 Perfil de {ctx.author.display_name}",
        color=discord.Color.dark_purple(),
    )
    embed.set_thumbnail(url=ctx.author.display_avatar.url)
    embed.add_field(name="🆙 Nível", value=str(nivel), inline=True)
    embed.add_field(name="✨ XP Total", value=str(xpTotal), inline=True)
    embed.add_field(
        name="🚀 Próximo nível",
        value=f"{xpProxNivel} XP para o nível {nivel + 1}",
        inline=False,
    )
    await ctx.send(embed=embed)


@bot.command()
async def ranking(ctx: commands.Context) -> None:
    """Exibe o Top 10 de usuários com maior XP no servidor."""
    dadosXp = carregarXp()
    guildId = str(ctx.guild.id) #ID do servidor

    # Pega apenas os dados do servidor atual
    dadosServidor = dadosXp.get(guildId, {})

    if not dadosServidor:
        await ctx.send(
            "Ninguém neste servidor tem XP ainda! Use `focobot.foco` para ser o primeiro!"
        )
        return

    # Ordena o ranking usando os dados apenas do servidor
    rankingOrdem = sorted(dadosServidor.items(), key=lambda item: item[1], reverse=True)
    top10 = rankingOrdem[:TOP_RANKING]

    MEDALHAS = {1: "🥇", 2: "🥈", 3: "🥉"}
    mensagem = "🏆 **Top 10 — Ranking de Foco do Servidor** 🏆\n\n"

    for posicao, (userIdStr, xpTotal) in enumerate(top10, start=1):
        membro = ctx.guild.get_member(int(userIdStr))
        nome = membro.display_name if membro else "Usuário desconhecido"
        nivel = xpTotal // XP_POR_NIVEL
        medalha = MEDALHAS.get(posicao, f"**{posicao}º**")
        mensagem += f"{medalha} **{nome}** — Nível {nivel} ({xpTotal} XP)\n"

    await ctx.send(mensagem)


@bot.command(name="help", aliases=["ajuda"])
async def comandoHelp(ctx: commands.Context) -> None:
    """Exibe todos os comandos disponíveis do FocoBOT."""
    embed = discord.Embed(
        title="📚 Ajuda — FocoBOT",
        description=(
            "Bem-vindo ao seu parceiro de foco! "
            "Abaixo estão todos os comandos disponíveis."
        ),
        color=discord.Color.dark_purple(),
    )
    embed.add_field(
        name="⏱️ focobot.foco [minutos]",
        value="Inicia uma sessão de foco e silencia você na call. (Ex: `focobot.foco 25`)",
        inline=False,
    )
    embed.add_field(
        name="🛑 focobot.cancelar",
        value="Cancela sua sessão atual de foco. *(Você perde o XP da sessão.)*",
        inline=False,
    )
    embed.add_field(
        name="⏳ focobot.status",
        value="Mostra quanto tempo falta para o **seu** foco acabar.",
        inline=False,
    )
    embed.add_field(
        name="📊 focobot.statusall",
        value="Lista o tempo restante de **todas** as pessoas focadas no servidor.",
        inline=False,
    )
    embed.add_field(
        name="🏆 focobot.perfil",
        value="Exibe seu nível, XP total e quanto falta para o próximo nível.",
        inline=False,
    )
    embed.add_field(
        name="🥇 focobot.ranking",
        value="Mostra o Top 10 dos usuários mais produtivos do servidor.",
        inline=False,
    )
    embed.add_field(
        name="🏓 focobot.ping",
        value="Verifica se o bot está online e respondendo.",
        inline=False,
    )
    embed.set_footer(
        text="Dica: Entre em um canal de voz antes de iniciar o foco para ser mutado automaticamente!"
    )
    await ctx.send(embed=embed)


#Entry point 
if __name__ == "__main__":
    bot.run(TOKEN, log_handler=None)  # log_handler=None para evitar logs duplicados