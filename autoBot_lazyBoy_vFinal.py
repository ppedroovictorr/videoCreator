import asyncio
import edge_tts
import pathlib
import subprocess
import sys
import time
import threading
import warnings
import json

FFMPEG_PATH = r"C:\ffmpeg\bin\ffmpeg.exe"  # Ajuste o caminho conforme necessário

VOZES = {
    "1": {  # Mulher
        "nome": "mulher",
        "imagem": "locutora.png",
        "idiomas": {
            "1": ("italiano", "it-IT-IsabellaNeural"),
            "2": ("croata", "hr-HR-GabrijelaNeural"),
            "3": ("ingles", "en-US-EmmaMultilingualNeural"),
            "4": ("portugues-br", "pt-BR-FranciscaNeural"),
            "5": ("portugues-pt", "pt-PT-RaquelNeural"),
            "6": ("servio", "sr-RS-SophieNeural"),
            "7": ("espanhol", "es-ES-ElviraNeural"),
            "8": ("ingles-uk", "en-GB-SoniaNeural"),
            "9": ("frances", "fr-FR-VivienneMultilingualNeural"),
        }
    },
    "2": {  # Homem
        "nome": "homem",
        "imagem": "locutor.png",
        "idiomas": {
            "1": ("italiano", "it-IT-DiegoNeural"),
            "2": ("croata", "hr-HR-SreckoNeural"),
            "3": ("ingles", "en-US-ChristopherNeural"),
            "4": ("portugues-br", "pt-BR-AntonioNeural"),
            "5": ("portugues-pt", "pt-PT-DuarteNeural"),
            "6": ("servio", "sr-RS-NicholasNeural"),
            "7": ("espanhol", "es-ES-AlvaroNeural"),
            "8": ("ingles-uk", "en-GB-RyanNeural"),
            "9": ("frances", "fr-FR-RemyMultilingualNeural"),
        }
    }
}

def limpar_pastas_temporarias(script_dir):
    import shutil
    for folder in script_dir.rglob("__pycache__"):
        shutil.rmtree(folder, ignore_errors=True)

def split_text_into_blocks(text, max_chars):
    words = text.split()
    blocks = []
    current_block = ""
    for word in words:
        if len(current_block) + len(word) + 1 > max_chars:
            blocks.append(current_block.strip())
            current_block = word
        else:
            current_block += " " + word
    if current_block:
        blocks.append(current_block.strip())
    return blocks

def transformar_texto_para_leitura_fluida(texto, max_chars_por_bloco=450):
    blocos = split_text_into_blocks(texto, max_chars_por_bloco)
    return '<break time="500ms"/>'.join(blocos)

def normalizar_nome_para_arquivo(nome):
    return nome.replace(' ', '_').replace('-', '_').lower()

def escolher_voz_e_imagem():
    print("Quem narra?")
    print("1 - Mulher")
    print("2 - Homem")
    escolha_sexo = input("Escolha (1 ou 2): ")
    sexo = VOZES[escolha_sexo]
    print("Digite a opcao do idioma para narracao:")
    for k, v in sexo["idiomas"].items():
        print(f"{k} - {v[0].capitalize()}")
    escolha_idioma = input("Escolha: ")
    idioma, voice = sexo["idiomas"][escolha_idioma]
    imagem = sexo["imagem"]
    return sexo["nome"], imagem, idioma, voice

def perguntar_efeitos():
    print("Aplicar efeitos visuais?")
    barulho = input("Barulho escuro? (s/n): ").lower() == 's'
    pendolo = input("Pêndulo? (s/n): ").lower() == 's'
    return {'barulho_escuro': barulho, 'pendolo': pendolo}

def perguntar_legenda():
    return input("Gerar legenda? (s/n): ").lower() == 's'

def formatar_tempo_ass(segundos):
    h = int(segundos // 3600)
    m = int((segundos % 3600) // 60)
    s = segundos % 60
    return f"{h:01d}:{m:02d}:{s:06.3f}"

def gerar_ass_legenda_whisper(resultado_whisper, caminho_ass):
    with open(caminho_ass, 'w', encoding='utf-8') as f:
        f.write("[Script Info]\n")
        f.write("Title: Legenda\n")
        f.write("ScriptType: v4.00+\n")
        f.write("WrapStyle: 0\n")
        f.write("ScaledBorderAndShadow: yes\n")
        f.write("[V4+ Styles]\n")
        f.write("Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n")
        f.write("Style: Default,Arial,20,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,2,2,10,10,10,1\n")
        f.write("[Events]\n")
        f.write("Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
        for segment in resultado_whisper['segments']:
            start = formatar_tempo_ass(segment['start'])
            end = formatar_tempo_ass(segment['end'])
            text = segment['text'].strip()
            f.write(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}\n")

def obter_duracao_audio(caminho_audio, ffprobe_path):
    try:
        result = subprocess.run([ffprobe_path, '-v', 'quiet', '-print_format', 'json', '-show_format', str(caminho_audio)], capture_output=True, text=True)
        data = json.loads(result.stdout)
        return float(data['format']['duration'])
    except:
        return None

def formatar_duracao(segundos):
    if segundos is None:
        return "N/A"
    h = int(segundos // 3600)
    m = int((segundos % 3600) // 60)
    s = int(segundos % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"

def barra_progresso(etapa, total=6):
    print(f"Progresso: {etapa}/{total}")

global stop_spinner
stop_spinner = False

def spinner():
    while not stop_spinner:
        for char in '|/-\\':
            sys.stdout.write(f'\r{char} Processando...')
            sys.stdout.flush()
            time.sleep(0.1)

def iniciar_status(mensagem):
    global stop_spinner
    stop_spinner = False
    thread = threading.Thread(target=spinner)
    thread.start()

def parar_status():
    global stop_spinner
    stop_spinner = True
    time.sleep(0.1)
    sys.stdout.write('\r' + ' ' * 20 + '\r')

async def main():
    script_dir = pathlib.Path(__file__).resolve().parent
    current_dir = pathlib.Path.cwd()
    historia_path = script_dir / "historia.txt"
    bruto_path = script_dir / "historia_bruto.mp3"
    with open(historia_path, 'r', encoding='utf-8') as f:
        texto = f.read()
    sexo_escolhido, imagem, idioma_escolhido, voice = escolher_voz_e_imagem()
    efeitos = perguntar_efeitos()
    legenda = perguntar_legenda()
    sexo_arquivo = normalizar_nome_para_arquivo(sexo_escolhido)
    idioma_arquivo = normalizar_nome_para_arquivo(idioma_escolhido)
    final_path = script_dir / f"historia_{sexo_arquivo}_{idioma_arquivo}.mp3"
    video_path = script_dir / f"historia_{sexo_arquivo}_{idioma_arquivo}.mp4"
    print("Etapa 1: transformando texto para leitura fluida...")
    barra_progresso(1)
    texto_transformado = transformar_texto_para_leitura_fluida(texto)
    print("Etapa 2: gerando audio bruto com edge-tts...")
    barra_progresso(2)
    iniciar_status("Gerando áudio bruto...")
    communicate = edge_tts.Communicate(texto_transformado, voice)
    await communicate.save(str(bruto_path))
    parar_status()
    print("Etapa 3: removendo silencios com FFmpeg...")
    barra_progresso(3)
    iniciar_status("Removendo silêncios...")
    subprocess.run([FFMPEG_PATH, '-i', str(bruto_path), '-af', 'silenceremove=stop_periods=-1:stop_duration=0.2:stop_threshold=-40dB', '-y', str(final_path)], cwd=script_dir)
    parar_status()
    ffprobe_path = FFMPEG_PATH.replace("ffmpeg.exe", "ffprobe.exe")
    dur_original = obter_duracao_audio(bruto_path, ffprobe_path)
    dur_cortado = obter_duracao_audio(final_path, ffprobe_path)
    print(f"Duracao do audio original: {formatar_duracao(dur_original)}")
    print(f"Duracao do audio cortado: {formatar_duracao(dur_cortado)}")
    if legenda:
        print("Etapa 4: gerando legenda com Whisper...")
        barra_progresso(4)
        iniciar_status("Transcrevendo com Whisper...")
        try:
            import whisper
            warnings.filterwarnings("ignore")
            model = whisper.load_model("base")
            result = model.transcribe(str(final_path), word_timestamps=True, verbose=False)
            gerar_ass_legenda_whisper(result, script_dir / "legenda_temp.ass")
        except ImportError:
            print("Erro: para a opcao B com legenda, instale openai-whisper.")
            legenda = False
        parar_status()
    else:
        barra_progresso(4)
    print("Etapa 5: gerando video com a imagem selecionada...")
    barra_progresso(5)
    iniciar_status("Gerando vídeo...")
    vf = "scale=854:480:force_original_aspect_ratio=decrease,pad=854:480:(ow-iw)/2:(oh-ih)/2:black"
    if efeitos['barulho_escuro']:
        vf = f"eq=brightness=-0.08:saturation=0.85,noise=alls=8:allf=t+u,vignette,{vf}"
    if efeitos['pendolo']:
        vf = f"rotate='0.02*sin(2*PI*t/6)':ow=rotw(iw):oh=roth(ih):c=black@0,{vf}"
    if legenda:
        vf += f",ass=legenda_temp.ass"
    subprocess.run([FFMPEG_PATH, '-y', '-loop', '1', '-framerate', '2', '-i', imagem, '-i', str(final_path), '-vf', vf, '-c:v', 'libx264', '-preset', 'ultrafast', '-tune', 'stillimage', '-pix_fmt', 'yuv420p', '-r', '2', '-c:a', 'aac', '-b:a', '128k', '-shortest', str(video_path)], cwd=script_dir)
    parar_status()
    barra_progresso(6)
    bruto_path.unlink(missing_ok=True)
    (script_dir / "legenda_temp.ass").unlink(missing_ok=True)
    limpar_pastas_temporarias(script_dir)
    print("Vídeo gerado com sucesso!")

if __name__ == "__main__":
    asyncio.run(main())