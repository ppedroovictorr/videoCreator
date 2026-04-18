# Opcao B: para legenda, instale com: pip install openai-whisper

import os
import pathlib
import re
import shutil
import asyncio
import subprocess
import edge_tts
import json
import warnings
import sys
import time
import threading

try:
    import whisper
except ImportError:
    whisper = None

FFMPEG_PATH = r"C:\ffmpeg\bin\ffmpeg.exe"
FFPROBE_PATH = FFMPEG_PATH.replace("ffmpeg.exe", "ffprobe.exe")

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
    for item in os.listdir(script_dir):
        item_path = script_dir / item
        if item_path.is_dir() and (item.startswith("tts_blocos_") or item.startswith("temp_audio_") or item == "temp_audio"):
            shutil.rmtree(item_path)

    # Remover arquivos temporários específicos, mas não mp3/mp4 finais ou legenda_temp.ass
    for file in script_dir.glob("historia_bruto.mp3"):
        if file.exists():
            file.unlink()

def split_text_into_blocks(text, max_chars):
    words = text.split()
    blocks = []
    current_block = ""
    for word in words:
        if len(current_block) + len(word) + 1 <= max_chars:
            current_block += word + " "
        else:
            if current_block:
                blocks.append(current_block.strip())
            current_block = word + " "
    if current_block:
        blocks.append(current_block.strip())
    return blocks

def transformar_texto_para_leitura_fluida(texto, max_chars_por_bloco=450):
    texto = texto.replace("\ufeff", "")  # Remove BOM
    paragrafos = re.split(r'\n\s*\n', texto)
    paragrafos_processados = []
    for paragrafo in paragrafos:
        paragrafo = paragrafo.strip()
        if not paragrafo:
            continue
        # Quebrar em frases usando pontuação
        frases = re.split(r'(?<=[.!?])\s+', paragrafo)
        bloco_atual = ""
        for frase in frases:
            frase = frase.strip()
            if not frase:
                continue
            if len(bloco_atual) + len(frase) + 1 <= max_chars_por_bloco:
                bloco_atual += frase + " "
            else:
                if bloco_atual:
                    paragrafos_processados.append(bloco_atual.strip())
                bloco_atual = frase + " "
        if bloco_atual:
            paragrafos_processados.append(bloco_atual.strip())
    return "\n\n".join(paragrafos_processados)

def normalizar_nome_para_arquivo(nome):
    nome = re.sub(r'[^a-zA-Z0-9]', '_', nome)
    return nome.lower()

def escolher_voz_e_imagem():
    print("Quem narra?")
    print("1 - Mulher")
    print("2 - Homem")
    sexo = input("Digite a opcao: ").strip()
    if sexo not in VOZES:
        print("Opcao invalida.")
        return None
    
    print("Digite a opcao do idioma para narracao:")
    print("1 - Italiano")
    print("2 - Croata")
    print("3 - Ingles")
    print("4 - Portugues-br")
    print("5 - Portugues-pt")
    print("6 - Servio")
    print("7 - Espanhol")
    print("8 - Ingles-UK")
    print("9 - Frances")
    idioma_opcao = input("Digite a opcao: ").strip()
    if idioma_opcao not in VOZES[sexo]["idiomas"]:
        print("Opcao invalida.")
        return None
    
    idioma, voz = VOZES[sexo]["idiomas"][idioma_opcao]
    imagem = VOZES[sexo]["imagem"]
    return VOZES[sexo]["nome"], idioma, voz, imagem

def perguntar_efeitos():
    print("Deseja adicionar efeitos ao video?")
    print("1 - Sim")
    print("2 - Nao")
    opcao = input("Digite a opcao: ").strip()
    if opcao == "2":
        return None
    elif opcao == "1":
        print("Qual efeito deseja adicionar?")
        print("1 - Barulho escuro")
        print("2 - Pendolo")
        print("3 - Zoom in e zoom out")
        print("4 - Barulho escuro + Pendolo")
        print("5 - Barulho escuro + Zoom in e zoom out")
        print("6 - Pendolo + Zoom in e zoom out")
        print("7 - Barulho escuro + Pendolo + Zoom in e zoom out")
        efeito_opcao = input("Digite a opcao: ").strip()
        efeitos = {
            "1": "barulho_escuro",
            "2": "pendolo",
            "3": "zoom_in_out",
            "4": "barulho_pendolo",
            "5": "barulho_zoom",
            "6": "pendolo_zoom",
            "7": "todos"
        }
        if efeito_opcao in efeitos:
            return efeitos[efeito_opcao]
        else:
            print("Opcao invalida.")
            return None
    else:
        print("Opcao invalida.")
        return None

def perguntar_legenda():
    print("Deseja adicionar legenda ao video?")
    print("1 - Sim")
    print("2 - Nao")
    opcao = input("Digite a opcao: ").strip()
    if opcao == "1":
        return True
    elif opcao == "2":
        return False
    else:
        print("Opcao invalida.")
        return None

def formatar_tempo_ass(segundos):
    horas = int(segundos // 3600)
    minutos = int((segundos % 3600) // 60)
    seg = int(segundos % 60)
    centesimos = int((segundos % 1) * 100)
    return f"{horas}:{minutos:02d}:{seg:02d}.{centesimos:02d}"

def gerar_ass_legenda_whisper(resultado_whisper, caminho_ass):
    with open(caminho_ass, 'w', encoding='utf-8') as f:
        f.write("[Script Info]\n")
        f.write("ScriptType: v4.00+\n")
        f.write("Collisions: Normal\n")
        f.write("PlayResX: 854\n")
        f.write("PlayResY: 480\n")
        f.write("\n[V4+ Styles]\n")
        f.write("Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n")
        f.write("Style: Default,Arial,24,&H00FFFF00,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,2,0,2,10,10,10,1\n")
        f.write("\n[Events]\n")
        f.write("Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
        for segment in resultado_whisper["segments"]:
            if "words" in segment:
                for word in segment["words"]:
                    start = formatar_tempo_ass(word["start"])
                    end = formatar_tempo_ass(word["end"])
                    text = word["word"].replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")
                    f.write(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}\n")

def obter_duracao_audio(caminho_audio):
    if not os.path.exists(FFPROBE_PATH):
        return None
    try:
        result = subprocess.run([
            FFPROBE_PATH, "-v", "quiet", "-print_format", "json", "-show_format", str(caminho_audio)
        ], capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        return float(data["format"]["duration"])
    except:
        return None

def formatar_duracao(segundos):
    if segundos is None:
        return "N/A"
    horas = int(segundos // 3600)
    minutos = int((segundos % 3600) // 60)
    seg = int(segundos % 60)
    return f"{horas:02d}:{minutos:02d}:{seg:02d}"

def barra_progresso(etapa_atual, total_etapas, titulo=""):
    progresso = int((etapa_atual / total_etapas) * 20)
    barra = "#" * progresso + "-" * (20 - progresso)
    print(f"[{barra}] {etapa_atual}/{total_etapas} - {titulo}")

class StatusRodape:
    def __init__(self):
        self.thread = None
        self.running = False
        self.mensagem = ""
        self.etapa_atual = 0
        self.total_etapas = 0

    def _spinner(self):
        spinners = ["-", "\\", "|", "/"]
        idx = 0
        while self.running:
            progresso = int((self.etapa_atual / self.total_etapas) * 20)
            barra = "#" * progresso + "-" * (20 - progresso)
            sys.stdout.write(f"\r[{barra}] {self.etapa_atual}/{self.total_etapas} | {self.mensagem} {spinners[idx]}")
            sys.stdout.flush()
            idx = (idx + 1) % len(spinners)
            time.sleep(0.2)

    def iniciar(self, mensagem, etapa_atual, total_etapas):
        self.mensagem = mensagem
        self.etapa_atual = etapa_atual
        self.total_etapas = total_etapas
        self.running = True
        self.thread = threading.Thread(target=self._spinner)
        self.thread.start()

    def parar(self, mensagem_final):
        self.running = False
        if self.thread:
            self.thread.join()
        progresso = int((self.etapa_atual / self.total_etapas) * 20)
        barra = "#" * progresso + "-" * (20 - progresso)
        print(f"\r[{barra}] {self.etapa_atual}/{self.total_etapas} - {mensagem_final}")

status_rodape = StatusRodape()

def iniciar_status_rodape(mensagem, etapa_atual, total_etapas):
    status_rodape.iniciar(mensagem, etapa_atual, total_etapas)

def parar_status_rodape(mensagem_final):
    status_rodape.parar(mensagem_final)

async def main():
    script_dir = pathlib.Path(__file__).resolve().parent
    current_dir = pathlib.Path.cwd()
    print(f"Diretorio do script: {script_dir}")
    print(f"Diretorio atual: {current_dir}")
    
    limpar_pastas_temporarias(script_dir)
    
    escolha = escolher_voz_e_imagem()
    if not escolha:
        return
    sexo_escolhido, idioma_escolhido, voice, imagem_nome = escolha
    
    efeitos = perguntar_efeitos()
    legenda = perguntar_legenda()
    if legenda is None:
        return
    
    sexo_arquivo = normalizar_nome_para_arquivo(sexo_escolhido)
    idioma_arquivo = normalizar_nome_para_arquivo(idioma_escolhido)
    imagem_path = script_dir / imagem_nome
    final_path = script_dir / f"historia_{sexo_arquivo}_{idioma_arquivo}.mp3"
    video_path = script_dir / f"historia_{sexo_arquivo}_{idioma_arquivo}.mp4"
    
    historia_path = script_dir / "historia.txt"
    if not historia_path.exists():
        print("Erro: arquivo historia.txt nao encontrado.")
        return
    
    with open(historia_path, 'r', encoding='utf-8') as f:
        texto_original = f.read().strip()
    
    if not texto_original:
        print("Erro: historia.txt esta vazio.")
        return
    
    if not imagem_path.exists():
        print(f"Erro: imagem {imagem_nome} nao encontrada.")
        return
    
    if not os.path.exists(FFMPEG_PATH):
        print("Erro: ffmpeg.exe nao encontrado.")
        return
    
    if not os.path.exists(FFPROBE_PATH):
        print("Aviso: ffprobe.exe nao encontrado. Duracoes nao serao exibidas.")
    
    bruto_path = script_dir / "historia_bruto.mp3"
    
    # Etapa 1: transformando texto
    print("Etapa 1: transformando texto para leitura fluida...")
    barra_progresso(1, 6, "Transformando texto")
    texto = transformar_texto_para_leitura_fluida(texto_original)
    
    # Etapa 2: gerando audio bruto
    print("Etapa 2: gerando audio bruto com edge-tts...")
    barra_progresso(2, 6, "Gerando audio bruto")
    iniciar_status_rodape("Gerando audio bruto...", 2, 6)
    communicate = edge_tts.Communicate(texto, voice)
    await communicate.save(str(bruto_path))
    parar_status_rodape("Audio bruto gerado.")
    
    # Etapa 3: removendo silencios
    print("Etapa 3: removendo silencios com FFmpeg...")
    barra_progresso(3, 6, "Removendo silencios")
    iniciar_status_rodape("Tirando/removendo silencio...", 3, 6)
    subprocess.run([
        FFMPEG_PATH, "-y", "-i", str(bruto_path), "-af", "silenceremove=stop_periods=-1:stop_duration=0.2:stop_threshold=-40dB", str(final_path)
    ], check=True)
    parar_status_rodape("Silencio removido.")
    
    # Etapa 4: obtendo duracoes
    print("Etapa 4: obtendo duracao dos audios...")
    barra_progresso(4, 6, "Obtendo duracoes")
    duracao_bruto = obter_duracao_audio(bruto_path)
    duracao_final = obter_duracao_audio(final_path)
    print(f"Duracao do audio original: {formatar_duracao(duracao_bruto)}")
    print(f"Duracao do audio cortado : {formatar_duracao(duracao_final)}")
    
    # Etapa 5: gerando legenda se solicitado
    if legenda:
        if whisper is None:
            print("Erro: para a opcao B com legenda, instale openai-whisper.")
            return
        print("Etapa 5: gerando legenda com Whisper...")
        barra_progresso(5, 6, "Gerando legenda")
        warnings.filterwarnings("ignore", message="FP16 is not supported on CPU")
        modelo_whisper = whisper.load_model("base")
        resultado_whisper = modelo_whisper.transcribe(str(final_path), word_timestamps=True, verbose=False)
        legenda_temp_path = script_dir / "legenda_temp.ass"
        gerar_ass_legenda_whisper(resultado_whisper, str(legenda_temp_path))
    else:
        barra_progresso(5, 6, "Pulando legenda")
    
    # Etapa 6: gerando video
    print("Etapa 6: gerando video com a imagem selecionada...")
    barra_progresso(6, 6, "Gerando video")
    vf = "scale=854:480:force_original_aspect_ratio=decrease,pad=854:480:(ow-iw)/2:(oh-ih)/2:black"
    if efeitos:
        if efeitos == "barulho_escuro":
            vf += ",eq=brightness=-0.08:saturation=0.85,noise=alls=8:allf=t+u,vignette"
        elif efeitos == "pendolo":
            vf += ",rotate='0.006*sin(2*PI*t/10)':ow=rotw(iw):oh=roth(ih):c=black@0,scale=854:480:force_original_aspect_ratio=decrease,pad=854:480:(ow-iw)/2:(oh-ih)/2:black"
        elif efeitos == "zoom_in_out":
            vf += ",zoompan=z='min(max(zoom,pzoom)+0.0015,1.5)':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=854x480"
        elif efeitos == "barulho_pendolo":
            vf += ",eq=brightness=-0.08:saturation=0.85,noise=alls=8:allf=t+u,vignette,rotate='0.006*sin(2*PI*t/10)':ow=rotw(iw):oh=roth(ih):c=black@0,scale=854:480:force_original_aspect_ratio=decrease,pad=854:480:(ow-iw)/2:(oh-ih)/2:black"
        elif efeitos == "barulho_zoom":
            vf += ",eq=brightness=-0.08:saturation=0.85,noise=alls=8:allf=t+u,vignette,zoompan=z='min(max(zoom,pzoom)+0.0015,1.5)':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=854x480"
        elif efeitos == "pendolo_zoom":
            vf += ",rotate='0.006*sin(2*PI*t/10)':ow=rotw(iw):oh=roth(ih):c=black@0,scale=854:480:force_original_aspect_ratio=decrease,pad=854:480:(ow-iw)/2:(oh-ih)/2:black,zoompan=z='min(max(zoom,pzoom)+0.0015,1.5)':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=854x480"
        elif efeitos == "todos":
            vf += ",eq=brightness=-0.08:saturation=0.85,noise=alls=8:allf=t+u,vignette,rotate='0.006*sin(2*PI*t/10)':ow=rotw(iw):oh=roth(ih):c=black@0,scale=854:480:force_original_aspect_ratio=decrease,pad=854:480:(ow-iw)/2:(oh-ih)/2:black,zoompan=z='min(max(zoom,pzoom)+0.0015,1.5)':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=854x480"
    if legenda:
        vf += ",ass=legenda_temp.ass"
    
    subprocess.run([
        FFMPEG_PATH, "-y", "-loop", "1", "-framerate", "2", "-i", str(imagem_path), "-i", str(final_path),
        "-vf", vf, "-c:v", "libx264", "-preset", "ultrafast", "-tune", "stillimage", "-pix_fmt", "yuv420p",
        "-r", "2", "-c:a", "aac", "-b:a", "128k", "-shortest", str(video_path)
    ], cwd=script_dir, check=True)
    
    # Limpeza final
    if bruto_path.exists():
        bruto_path.unlink()
    legenda_temp_path = script_dir / "legenda_temp.ass"
    if legenda_temp_path.exists():
        legenda_temp_path.unlink()
    limpar_pastas_temporarias(script_dir)
    
    print("Video gerado com sucesso!")

if __name__ == "__main__":
    asyncio.run(main())