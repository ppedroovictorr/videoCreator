import os
import pathlib
import re
import shutil
import asyncio
import subprocess
import edge_tts

FFMPEG_PATH = r"C:\ffmpeg\bin\ffmpeg.exe"

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
    for item in script_dir.iterdir():
        if item.is_dir() and (
            item.name.startswith("tts_blocos_")
            or item.name.startswith("temp_audio_")
            or item.name == "temp_audio"
        ):
            try:
                shutil.rmtree(item, ignore_errors=True)
                print(f"Pasta temporaria removida: {item.name}")
            except Exception as e:
                print(f"Erro ao remover a pasta temporaria '{item.name}': {e}")


def split_text_into_blocks(text, max_chars):
    words = text.split()
    blocks = []
    current_block = ""

    for word in words:
        if len(current_block) + len(word) + 1 <= max_chars:
            current_block += (" " if current_block else "") + word
        else:
            blocks.append(current_block.strip())
            current_block = word

    if current_block:
        blocks.append(current_block.strip())

    return blocks


def transformar_texto_para_leitura_fluida(texto, max_chars_por_bloco=450):
    texto = texto.replace("\ufeff", "")
    texto = texto.replace("\r\n", "\n").replace("\r", "\n")

    paragrafos = re.split(r"\n\s*\n+", texto.strip())
    paragrafos_tratados = []

    for paragrafo in paragrafos:
        if not paragrafo.strip():
            continue

        blocos = split_text_into_blocks(paragrafo, max_chars_por_bloco)
        paragrafo = " ".join(blocos)

        paragrafo = re.sub(r"\s+([,;:!?])", r"\1", paragrafo)
        paragrafo = re.sub(r"\s+\.", ".", paragrafo)

        paragrafo = re.sub(
            r'(?<!\d)([.!?…])(?=(?:["“”\'‘’(\[])?[A-Za-zÀ-ÖØ-öø-ÿ])',
            r'\1 ',
            paragrafo
        )

        paragrafo = re.sub(r"\s{2,}", " ", paragrafo).strip()
        paragrafos_tratados.append(paragrafo)

    return "\n\n".join(paragrafos_tratados)


def normalizar_nome_para_arquivo(nome):
    nome = nome.lower().strip()
    nome = nome.replace("-", "_")
    nome = nome.replace(" ", "_")
    return nome


def escolher_voz_e_imagem():
    print("Quem narra?")
    print("1 - Mulher")
    print("2 - Homem")

    opcao_sexo = input("Opcao: ").strip()

    if opcao_sexo not in VOZES:
        print("Erro: opcao invalida para narrador.")
        return None

    print()
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

    opcao_idioma = input("Opcao: ").strip()

    if opcao_idioma not in VOZES[opcao_sexo]["idiomas"]:
        print("Erro: opcao invalida para idioma.")
        return None

    sexo = VOZES[opcao_sexo]["nome"]
    imagem = VOZES[opcao_sexo]["imagem"]
    idioma, voz = VOZES[opcao_sexo]["idiomas"][opcao_idioma]

    return sexo, idioma, voz, imagem


async def main():
    try:
        script_dir = pathlib.Path(__file__).resolve().parent
        current_dir = pathlib.Path.cwd()

        historia_path = script_dir / "historia.txt"
        bruto_path = script_dir / "historia_bruto.mp3"

        print(f"Diretorio do script      : {script_dir}")
        print(f"Diretorio de execucao    : {current_dir}")
        print(f"Caminho de historia.txt  : {historia_path}")
        print()

        limpar_pastas_temporarias(script_dir)

        escolha = escolher_voz_e_imagem()
        if not escolha:
            return

        sexo_escolhido, idioma_escolhido, voice, imagem_nome = escolha

        sexo_arquivo = normalizar_nome_para_arquivo(sexo_escolhido)
        idioma_arquivo = normalizar_nome_para_arquivo(idioma_escolhido)

        imagem_path = script_dir / imagem_nome
        final_path = script_dir / f"historia_{sexo_arquivo}_{idioma_arquivo}.mp3"
        video_path = script_dir / f"historia_{sexo_arquivo}_{idioma_arquivo}.mp4"

        print()
        print(f"Narrador selecionado     : {sexo_escolhido}")
        print(f"Idioma selecionado       : {idioma_escolhido}")
        print(f"Voz selecionada          : {voice}")
        print(f"Imagem selecionada       : {imagem_nome}")
        print()

        if not historia_path.exists():
            print("Erro: O arquivo 'historia.txt' nao foi encontrado na pasta do script.")
            return

        if not imagem_path.exists():
            print(f"Erro: O arquivo '{imagem_nome}' nao foi encontrado na pasta do script.")
            return

        with open(historia_path, "r", encoding="utf-8") as f:
            texto_original = f.read()

        if not texto_original.strip():
            print("Erro: O arquivo 'historia.txt' esta vazio.")
            return

        if not os.path.exists(FFMPEG_PATH):
            print(f"Erro: ffmpeg.exe nao encontrado em '{FFMPEG_PATH}'.")
            return

        texto = transformar_texto_para_leitura_fluida(texto_original)

        if not texto.strip():
            print("Erro: O texto transformado ficou vazio.")
            return

        print("Etapa 1: transformando texto para leitura fluida...")
        print("Etapa 2: gerando audio bruto com edge-tts...")

        communicate = edge_tts.Communicate(texto, voice)
        await communicate.save(str(bruto_path))

        if not bruto_path.exists():
            print("Erro: o audio bruto nao foi gerado.")
            return

        print("Etapa 3: removendo silencios com FFmpeg...")

        cmd_audio = [
            FFMPEG_PATH,
            "-i", str(bruto_path),
            "-af", "silenceremove=stop_periods=-1:stop_duration=0.2:stop_threshold=-40dB",
            "-y",
            str(final_path)
        ]

        result_audio = subprocess.run(cmd_audio, capture_output=True, text=True)

        if result_audio.returncode != 0:
            print("Erro ao processar o audio com FFmpeg:")
            print(result_audio.stderr)
            return

        if not final_path.exists():
            print("Erro: o arquivo final sem silencio nao foi criado.")
            return

        print("Etapa 4: gerando video com a imagem selecionada...")

        cmd_video = [
            FFMPEG_PATH,
            "-y",
            "-loop", "1",
            "-framerate", "2",
            "-i", str(imagem_path),
            "-i", str(final_path),
            "-vf", "scale=854:480:force_original_aspect_ratio=decrease,pad=854:480:(ow-iw)/2:(oh-ih)/2:black",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-tune", "stillimage",
            "-pix_fmt", "yuv420p",
            "-r", "2",
            "-c:a", "aac",
            "-b:a", "128k",
            "-shortest",
            str(video_path)
        ]

        result_video = subprocess.run(cmd_video, capture_output=True, text=True)

        if result_video.returncode != 0:
            print("Erro ao gerar o video com FFmpeg:")
            print(result_video.stderr)
            return

        if not video_path.exists():
            print("Erro: o arquivo de video nao foi criado.")
            return

        if bruto_path.exists():
            bruto_path.unlink()

        limpar_pastas_temporarias(script_dir)

        print()
        print("Processo concluido com sucesso.")
        print(f"Arquivo de audio final: {final_path.name}")
        print(f"Arquivo de video final: {video_path.name}")
        print("Observacao: agora o script escolhe automaticamente locutora.png ou locutor.png conforme o sexo do narrador.")

    except Exception as e:
        print(f"Erro inesperado: {e}")


if __name__ == "__main__":
    asyncio.run(main())