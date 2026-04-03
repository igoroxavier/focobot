# 🧠 FocoBOT

O **FocoBOT** é um bot para Discord desenvolvido em Python que usa a técnica Pomodoro com gamificação. Ele foi criado para ajudar estudantes a manterem o foco silenciando distrações e recompensando a produtividade com XP, níveis e rankings.

## 🚀 Funcionalidades Principais

* **Modo Foco Automático:** Silencia (Mute e Deafen) o usuário em canais de voz durante o tempo determinado.
* **Sistema de Progressão:** Usuários ganham XP baseado no tempo de foco e sobem de nível.
* **Competição Saudável:** Rankings locais e globais isolados por servidor (`guild_id`).
* **Proteção de Dados:** Prevenção de *Race Conditions* com `asyncio.Lock` durante leitura/escrita no banco de dados.

## 🛠️ Tecnologias Utilizadas

* **Linguagem:** Python
* **Biblioteca Principal:** `discord.py`
* **Assincronismo:** `asyncio`
* **Banco de Dados:** Arquivo local `JSON` estruturado por servidor.

## 💻 Lista de Comandos

| Comando | Descrição |
| :--- | :--- |
| `focobot.foco [minutos]` | Inicia uma sessão de foco e muta o usuário na call. |
| `focobot.cancelar` | Interrompe o cronômetro, devolve a voz e anula o XP da sessão. |
| `focobot.status` | Exibe o tempo exato restante do seu foco atual. |
| `focobot.statusall` | Lista todos os usuários do servidor que estão focados no momento. |
| `focobot.perfil` | Mostra o nível, XP total e o progresso para o próximo nível. |
| `focobot.ranking` | Exibe o Top 10 dos usuários com mais tempo de estudo no servidor. |
| `focobot.ajuda` | Mostra o menu de comandos e informações de uso. |

## ⚙️ Como Rodar Localmente

1. Clone este repositório:
   ```bash
   git clone [https://github.com/igoroxavier/focobot.git](https://github.com/igoroxavier/focobot.git)

2. Instale as dependências:
   pip install -r requirements.txt

3. Crie um arquivo .env na raiz do projeto e adicione o token do seu bot:
   DISCORD_TOKEN="token"
