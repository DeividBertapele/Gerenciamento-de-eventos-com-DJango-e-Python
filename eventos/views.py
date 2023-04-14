import csv
import os
import sys
from io import BytesIO
from secrets import token_urlsafe

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.messages import constants
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from PIL import Image, ImageDraw, ImageFont

from .models import Certificado, Evento


@login_required
def novo_evento(request):
    if request.method == "GET":
        return render(request, 'novo_evento.html')
    elif request.method == "POST":
        nome = request.POST.get('nome')
        descricao = request.POST.get('descricao')
        data_inicio = request.POST.get('data_inicio')
        data_termino = request.POST.get('data_termino')
        carga_horaria = request.POST.get('carga_horaria')

        cor_principal = request.POST.get('cor_principal')
        cor_secundaria = request.POST.get('cor_secundaria')
        cor_fundo = request.POST.get('cor_fundo')

        logo = request.FILES.get('logo')

        evento = Evento(
            criador=request.user,
            nome=nome,
            descricao=descricao,
            data_inicio=data_inicio,
            data_termino=data_termino,
            carga_horaria=carga_horaria,
            cor_principal=cor_principal,
            cor_secundaria=cor_secundaria,
            cor_fundo=cor_fundo,
            logo=logo,
        )

        evento.save()

        messages.add_message(request, constants.SUCCESS, 'Evento cadastrado com sucesso') # noqa
        return redirect(reverse('novo_evento')) # noqa


@login_required
def gerenciar_evento(request):
    if request.method == "GET":
        nome = request.GET.get('nome')
        eventos = Evento.objects.filter(criador=request.user)

        if nome:
            eventos = eventos.filter(nome__contains=nome)

        return render(request, 'gerenciar_evento.html', {"eventos": eventos}) # noqa


@login_required
def inscrever_evento(request, id):
    evento = get_object_or_404(Evento, id=id)
    if request.method == "GET":
        return render(request, 'inscrever_evento.html', {'evento': evento}) # noqa
    elif request.method == "POST":
        # Validar se o usuário já é um participante
        evento.participantes.add(request.user)
        evento.save()

        messages.add_message(request, constants.SUCCESS, 'Inscrição realizada com sucesso.') # noqa
        return redirect(reverse('inscrever_evento', kwargs={'id': id})) # noqa


def participantes_evento(request, id):
    evento = get_object_or_404(Evento, id=id)
    if not evento.criador == request.user:
        raise Http404('Esse evento não é seu')

    if request.method == "GET":
        participantes = evento.participantes.all()
        return render(request, 'participantes_evento.html', {'evento': evento, 'participantes': participantes}) # noqa


def gerar_csv(request, id):
    evento = get_object_or_404(Evento, id=id)
    if not evento.criador == request.user:
        raise Http404('Esse evento não é seu')
    participantes = evento.participantes.all()

    token = f'{token_urlsafe(6)}.csv'
    path = os.path.join(settings.MEDIA_ROOT, token)

    with open(path, 'w') as arq:
        writer = csv.writer(arq, delimiter=",")
        for participante in participantes:
            x = (participante.username, participante.email)
            writer.writerow(x)

    return redirect(f'/media/{token}')


def certificados_evento(request, id):
    evento = get_object_or_404(Evento, id=id)
    if not evento.criador == request.user:
        raise Http404('Esse evento não é seu')

    if request.method == "GET":
        qtd_certificados = evento.participantes.all().count() - Certificado.objects.filter(evento=evento).count() # noqa
        return render(request, "certificados_evento.html",
                      {"evento": evento, "qtd_certificados": qtd_certificados}) # noqa


def gerar_certificado(request, id):
    evento = get_object_or_404(Evento, id=id)
    if not evento.criador == request.user:
        raise Http404('Esse evento não é seu')

    path_template = os.path.join(settings.BASE_DIR, 'templates/static/evento/img/template_certificado.png') # noqa
    path_fonte = os.path.join(settings.BASE_DIR, 'templates/static/fontes/arimo.ttf') # noqa

    for participante in evento.participantes.all():
        # Validar se já existe certificado desse participante para esse evento
        img = Image.open(path_template)
        path_template = os.path.join(settings.BASE_DIR, 'templates/static/evento/img/template_certificado.png') # noqa
        draw = ImageDraw.Draw(img)

        # Vamos configurar o tamanho da fonte no certificado
        fonte_nome = ImageFont.truetype(path_fonte, 60)
        fonte_info = ImageFont.truetype(path_fonte, 30)

        # Configurar as coordenadas e cor do texto no certificado
        draw.text((230, 651), f"{participante.username}", font=fonte_nome, fill=(0, 0, 0)) # noqa
        draw.text((761, 782), f"{evento.nome}", font=fonte_info, fill=(0, 0, 0)) # noqa
        draw.text((816, 849), f"{evento.carga_horaria} horas", font=fonte_info, fill=(0, 0, 0)) # noqa

        # Salvar as imagens e gerar o certificado dentro do diretório
        output = BytesIO()
        img.save(output, format="PNG", quality=100)
        output.seek(0)

        img_final = InMemoryUploadedFile(
            output,
            'ImageField',
            f'{token_urlsafe(8)}.png',
            'image/jpeg',
            sys.getsizeof(output),
            None,
        )
        certificado_gerado = Certificado(
            certificado=img_final,
            participante=participante,
            evento=evento,
        )
        certificado_gerado.save()

    messages.add_message(request, constants.SUCCESS, 'Certificados gerados com sucesso') # noqa
    return redirect(reverse('certificados_evento', kwargs={'id': evento.id})) # noqa


def procurar_certificado(request, id):
    evento = get_object_or_404(Evento, id=id)
    if not evento.criador == request.user:
        raise Http404('Esse evento não é seu')

    email = request.POST.get('email')
    certificado = Certificado.objects.filter(evento=evento).filter(participante__email=email).first() # noqa

    if not certificado:
        messages.add_message(request, constants.WARNING, 'Certificado não encontrado') # noqa
        return redirect(reverse('certificados_evento', kwargs={'id': evento.id})) # noqa

    return redirect(certificado.certificado.url) # noqa