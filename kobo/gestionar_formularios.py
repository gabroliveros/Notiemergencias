# -*- coding: utf-8 -*-
"""
Carga y despliega XLSForms en KoboToolbox vía API, sin intervención manual
en la interfaz web. Adaptado del código de gestión de formularios ya en uso
en otro proyecto del usuario — misma lógica (importar -> obtener asset UID ->
desplegar), ajustado a la estructura de este repo:
  - Los XLSForm se generan con kobo/xlsform_builder.py en la carpeta xlsforms/
  - Este módulo los sube y despliega usando el API token del usuario.

Uso típico:
    from kobo.gestionar_formularios import upload_koboform

    resultado = upload_koboform('noticias_emergencia', SERVER, API_TOKEN)
    # resultado = (import_url, asset_uid, deploy_ok)

Para volver a desplegar un formulario ya existente (por ejemplo tras cambiar
el XLSForm), pasa el asset_uid actual: se borran sus respuestas y el asset
viejo antes de recrearlo con la versión nueva.
"""

import os
import time

# Debe terminar en '/', ej: 'https://kf.kobotoolbox.org/'
SERVER_DEFAULT = 'https://kf.kobotoolbox.org/'


def upload_koboform(file, server=SERVER_DEFAULT, api_token=None, asset_uid=None):
    """
    file: nombre del XLSForm sin extensión (ej: 'noticias_emergencia'),
          debe existir en <raiz_del_repo>/xlsforms/<file>.xlsx
    server: URL base del servidor Kobo, con '/' final.
    api_token: token de la cuenta de KoboToolbox (kf.kobotoolbox.org/token/?format=json).
    asset_uid: si ya existe un formulario desplegado y se quiere reemplazar,
               pasar su UID (se elimina junto con sus respuestas antes de recrear).

    Devuelve (upload_url, asset_uid, deploy_ok) en caso de éxito, o un string
    con el mensaje de error en caso de falla.
    """
    kobo_server_url = server
    import_url = None

    nombre = file + '.xlsx'

    # Ruta al XLSForm: <raiz_del_repo>/xlsforms/<file>.xlsx
    basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    kobo_form_xlsx = os.path.join(basedir, 'xlsforms', nombre)

    if not os.path.exists(kobo_form_xlsx):
        # Si falta el XLSForm, tratar de generarlo automáticamente.
        from kobo.xlsform_builder import (
            generar_xlsform_noticias, 
            generar_xlsform_metricas_alerta,
            generar_xlsform_precipitacion_nacional,
            generar_xlsform_sismos
        )

        os.makedirs(os.path.join(basedir, 'xlsforms'), exist_ok=True)
        if file in ('noticias_emergencia', 'noticias_emergencia'):
            print(f'No se encontró {kobo_form_xlsx}. Generando XLSForm automáticamente.')
            generar_xlsform_noticias(kobo_form_xlsx)
        elif file in ('metricas_alerta', 'metricas_alerta'):
            print(f'No se encontró {kobo_form_xlsx}. Generando XLSForm automáticamente.')
            generar_xlsform_metricas_alerta(kobo_form_xlsx)
        elif file in ('precipitacion_nacional',):
            print(f'No se encontró {kobo_form_xlsx}. Generando XLSForm automáticamente.')
            generar_xlsform_precipitacion_nacional(kobo_form_xlsx)
        elif file in ('sismos_nacional',):
            print(f'No se encontró {kobo_form_xlsx}. Generando XLSForm automáticamente.')
            generar_xlsform_sismos(kobo_form_xlsx)

        if not os.path.exists(kobo_form_xlsx):
            alt_path = os.path.join(basedir, 'kobo', nombre)
            if os.path.exists(alt_path):
                kobo_form_xlsx = alt_path
            else:
                return f'No se encontró el XLSForm en {kobo_form_xlsx}. Genéralo primero con kobo/xlsform_builder.py.'

    if not api_token:
        return 'Falta api_token. Consíguelo en {server}token/?format=json estando logueado.'.format(server=server)

    headers = {
        'Authorization': f'Token {api_token}',
        'Accept': 'application/json',
    }

    import requests  # Importación perezosa

    max_attempts = 3

    # 0. ELIMINAR RESPUESTAS (BD) Y LUEGO EL ASSET (cuando hay uno previo)
    if asset_uid not in [None, 'None', '']:
        submissions_url = f'{kobo_server_url}api/v2/assets/{asset_uid}/data/'
        page_url = submissions_url
        submission_ids = []

        while page_url:
            submissions_resp = requests.get(page_url, params={'page_size': 1000}, headers=headers)
            if submissions_resp.status_code == 404:
                asset_uid = None
                break
            if submissions_resp.status_code != 200:
                return f'Error al obtener respuestas para eliminación: {submissions_resp.status_code} - {submissions_resp.text}'

            data = submissions_resp.json()
            submission_ids.extend([item['_id'] for item in data.get('results', []) if '_id' in item])
            page_url = data.get('next')

        if asset_uid and submission_ids:
            delete_data_url = f'{kobo_server_url}api/v2/assets/{asset_uid}/data/bulk/'
            bulk_delete = requests.delete(
                delete_data_url,
                headers={**headers, 'Content-Type': 'application/json'},
                json={'payload': {'submission_ids': submission_ids}},
            )
            if bulk_delete.status_code not in [200, 204]:
                return f'Error al eliminar respuestas: {bulk_delete.status_code} - {bulk_delete.text}'
            time.sleep(10)  # Dar tiempo para que Kobo procese la eliminación

            delete_url = f'{kobo_server_url}api/v2/assets/{asset_uid}/'
            delete_response = requests.delete(delete_url, headers=headers)
            if delete_response.status_code not in [200, 204, 202]:
                return f'Error eliminando asset: {delete_response.status_code} - {delete_response.text}'

            asset_uid = None
            time.sleep(5)


    # 1. IMPORTAR XLSFORM COMO ASSET NUEVO (vía /api/v2/imports/)

    imports_url = f'{kobo_server_url}api/v2/imports/'

    try:
        with open(kobo_form_xlsx, 'rb') as form:
            response = requests.post(
                imports_url,
                data={
                    'name': file,
                    'desired_type': 'survey',
                    'library': 'false',
                },
                files={
                    'file': (
                        os.path.basename(kobo_form_xlsx),
                        form,
                        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                    )
                },
                headers=headers,
                timeout=60,
            )
    except requests.exceptions.RequestException as e:
        return f'Error creando import Kobo: {e}'

    if not response.ok:
        return f'Error creando import Kobo: {response.status_code} - {response.text}'

    import_uid = response.json().get('uid')
    if not import_uid:
        return f'Kobo no devolvió UID del import: {response.json()}'

    # 1b. Esperar a que el import termine de procesar (es asíncrono)
    import_status_url = f'{kobo_server_url}api/v2/imports/{import_uid}/'
    import_result = None
    for _ in range(15):
        poll = requests.get(import_status_url, headers=headers, timeout=20)
        if not poll.ok:
            return f'Error consultando estado del import: {poll.status_code} - {poll.text}'
        import_result = poll.json()
        if import_result.get('status') != 'processing':
            break
        time.sleep(2)

    if import_result is None or import_result.get('status') != 'complete':
        return f'El import no se completó correctamente: {import_result}'

    creados = import_result.get('messages', {}).get('created', [])
    asset_ref = creados[0] if creados else None

    if not asset_ref or not asset_ref.get('uid'):
        return f'El import no generó un asset nuevo: {import_result}'

    asset_uid = asset_ref['uid']

    detalle = requests.get(
        f'{kobo_server_url}api/v2/assets/{asset_uid}/',
        headers=headers,
        timeout=20,
    )

    if not detalle.ok:
        return f'No se pudo consultar asset creado: {detalle.text}'

    asset_info = detalle.json()

    if asset_info.get('asset_type') != 'survey':
        return (
            f'Kobo creó un asset incorrecto: '
            f"{asset_info.get('asset_type')} UID={asset_uid}"
        )

    upload_url = imports_url


    # 2. DESPLEGAR EL ASSET (formulario)

    # print('\nASSET UID PARA DEPLOY:')
    # print(asset_uid)

    deploy_url = f'{kobo_server_url}api/v2/assets/{asset_uid}/deployment/'
    deploy_response = None
    try:
        deploy_response = requests.post(deploy_url, headers=headers, json={'active': True}, timeout=30)
        if not deploy_response.ok and deploy_response.status_code >= 500:
            deploy_response = requests.post(deploy_url, headers=headers, json={'active': True}, timeout=20)
    except requests.exceptions.RequestException as e:
        return f'Error al desplegar el formulario: {e}'

    if deploy_response is None or not deploy_response.ok:
        deploy_text = deploy_response.text if deploy_response is not None else '<sin respuesta>'
        return f'Error desplegando el formulario en Kobo: {getattr(deploy_response, "status_code", "?")} - {deploy_text}'

    if deploy_response.status_code not in (200, 201, 202):
        return f'Error desplegando el formulario en Kobo: {deploy_response.status_code} - {deploy_response.text}'


    # 3. Confirmar deployment__uuid disponible

    asset_detail = None
    for _ in range(8):
        asset_detail = requests.get(f'{kobo_server_url}api/v2/assets/{asset_uid}/', headers=headers, timeout=20)
        if not asset_detail.ok:
            return f'Error al obtener detalles del asset después del despliegue: {asset_detail.status_code} - {asset_detail.text}'
        if asset_detail.json().get('deployment__uuid'):
            break
        time.sleep(3)

    if not asset_detail or not asset_detail.json().get('deployment__uuid'):
        return f'El formulario se desplegó, pero no se obtuvo deployment__uuid tras el despliegue. Asset uid: {asset_uid}'

    return (upload_url, asset_uid, True)


# --------------------------------------------------------------------------
# ENVÍO DE DATOS (submissions) — PENDIENTE DE VERIFICAR
# --------------------------------------------------------------------------

import uuid as _uuid_module
import xml.etree.ElementTree as ET


def buscar_formulario(form_id, api_token, server=SERVER_DEFAULT):
    """Busca, entre los formularios desplegados del usuario, el que tiene
    name == form_id (usamos el mismo valor para form_title/id_string al
    generar los XLSForm, ver kobo/xlsform_builder.py). Devuelve el dict del
    asset (con su 'uid', etc.) o None si no existe todavía.

    NOTA: usa /api/v2/assets/ — el API v1 (kc.kobotoolbox.org) que usaba
    antes fue retirado permanentemente el 2 de junio de 2026 (HTTP 410)."""
    import requests

    headers = {'Authorization': f'Token {api_token}', 'Accept': 'application/json'}
    try:
        resp = requests.get(
            f'{server}api/v2/assets/',
            params={'name': form_id},
            headers=headers,
            timeout=15,
        )
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise RuntimeError(
            f"Error de conexión al intentar listar assets en {server}api/v2/assets/: {e}.\n"
            "Revisa tu conexión a Internet, configuración de proxy/DNS, y el valor 'kobo.server' en env_prod.json."
        )

    while True:
        for asset in resp.json().get('results', []):
            if (
                asset.get('name') == form_id
                and asset.get('asset_type') == 'survey'
                and asset.get('has_deployment') is True
            ):
                return asset

        next_url = resp.json().get('next')
        if not next_url:
            break

        resp = requests.get(next_url, headers=headers, timeout=15)
        resp.raise_for_status()

    return None


def formulario_existe(form_id, api_token, server=SERVER_DEFAULT):
    """True si ya hay un formulario desplegado con ese nombre."""
    return buscar_formulario(form_id, api_token, server) is not None


def obtener_asset_uid(form_id, api_token, server=SERVER_DEFAULT):
    """Devuelve el 'uid' del asset (formulario) cuyo name == form_id."""
    form = buscar_formulario(form_id, api_token, server)
    if form is None:
        raise ValueError(
            f"No se encontró un formulario desplegado con name='{form_id}' en "
            f"{server}api/v2/assets/. ¿Ya lo desplegaste con upload_koboform()?"
        )
    return form['uid']


def obtener_formhub_uuid(form_id, api_token, server=SERVER_DEFAULT):
    """
    Devuelve el 'formhub uuid' del formulario (necesario para el XML de cada
    submission). En v1 salía del campo 'uuid' de /api/v1/forms (ya no existe);
    en v2, según la tabla de migración oficial de Kobo, el mismo valor se
    expone como 'deployment__uuid' en el detalle del asset.
    """
    import requests

    asset_uid = obtener_asset_uid(form_id, api_token, server)
    headers = {'Authorization': f'Token {api_token}', 'Accept': 'application/json'}
    resp = requests.get(f'{server}api/v2/assets/{asset_uid}/', headers=headers)
    resp.raise_for_status()

    formhub_uuid = resp.json().get('deployment__uuid')
    if not formhub_uuid:
        raise ValueError(
            f"El formulario '{form_id}' (uid={asset_uid}) no tiene 'deployment__uuid' "
            'en su respuesta — puede que no esté desplegado todavía.'
        )
    return formhub_uuid


def _url_submission_openrosa(username, server=SERVER_DEFAULT):
    """URL del endpoint OpenRosa clásico, ligado al usuario, que sigue vivo
    en kc.kobotoolbox.org (o kc-eu.kobotoolbox.org para el servidor EU) —
    confirmado a mano: .../{username}/bulk-submission-form carga bien; este
    es su hermano singular (un XML por request, en vez de un ZIP)."""
    server_kc = server.replace('kf.kobotoolbox.org', 'kc.kobotoolbox.org').replace('eu.kobotoolbox.org', 'kc-eu.kobotoolbox.org')
    return f'{server_kc}{username}/submission'


def _construir_xml_submission(form_id, formhub_uuid, campos):
    """Arma el XML de una submission en formato OpenRosa. Usa ElementTree
    (no concatenación de strings) para escapar bien caracteres como '&' en
    URLs, que de otra forma romperían el XML."""
    root = ET.Element(form_id, attrib={'id': form_id})

    formhub = ET.SubElement(root, 'formhub')
    ET.SubElement(formhub, 'uuid').text = formhub_uuid

    for nombre, valor in campos.items():
        if valor is None or valor == '':
            continue
        ET.SubElement(root, nombre).text = str(valor)

    meta = ET.SubElement(root, 'meta')
    ET.SubElement(meta, 'instanceID').text = f'uuid:{_uuid_module.uuid4()}'

    return ET.tostring(root, encoding='unicode')


def enviar_submission(form_id, campos, api_token, username, formhub_uuid=None, server=SERVER_DEFAULT):
    """
    Envía UNA submission (una fila de datos) al formulario `form_id`, usando
    el endpoint OpenRosa clásico ligado al usuario (`username` = tu usuario
    de Kobo, el mismo que aparece en tu URL de 'bulk-submission-form').
    `campos` es un dict {nombre_de_campo_xlsform: valor}. Los campos
    select_one deben venir ya con el 'name' del choice (no el label) —
    ver kobo.xlsform_builder.nombre_choice.

    NOTA: todavía no probado con un envío real — probar con 1-2 registros
    antes de un envío masivo y revisar status_code/texto si falla.
    """
    import requests

    if formhub_uuid is None:
        formhub_uuid = obtener_formhub_uuid(form_id, api_token, server)

    xml_str = _construir_xml_submission(form_id, formhub_uuid, campos)
    headers = {'Authorization': f'Token {api_token}'}
    files = {'xml_submission_file': ('submission.xml', xml_str.encode('utf-8'), 'text/xml')}
    url = _url_submission_openrosa(username, server)

    return requests.post(url, headers=headers, files=files)


def enviar_filas(form_id, filas, api_token, username, server=SERVER_DEFAULT, pausa_segundos=0.3):
    """
    Envía varias filas (lista de dicts, ya preparadas con los nombres exactos
    de campo/choice del XLSForm) al formulario `form_id`.
    Devuelve la lista de errores: [(indice, status_code, texto), ...] (vacía si todo OK).
    """
    formhub_uuid = obtener_formhub_uuid(form_id, api_token, server)

    errores = []
    for i, campos in enumerate(filas):
        resp = enviar_submission(form_id, campos, api_token, username, formhub_uuid=formhub_uuid, server=server)
        if resp.status_code not in (200, 201):
            errores.append((i, resp.status_code, resp.text))
        time.sleep(pausa_segundos)  # evitar saturar el servidor

    print(f'Enviadas {len(filas) - len(errores)} de {len(filas)} filas a "{form_id}". Errores: {len(errores)}')
    return errores


def asegurar_formulario_desplegado(nombre_xlsform, form_id, api_token, server=SERVER_DEFAULT):
    """
    Garantiza que el formulario exista en Kobo, SIN BORRAR NADA si ya existe:
      - Si NO existe: lo crea y despliega con upload_koboform() (primera vez).
      - Si YA existe: no hace nada (no lo recrea, no borra sus respuestas).

    nombre_xlsform: nombre del XLSForm sin extensión (ej: 'noticias_emergencia'),
                    debe existir en <raiz_del_repo>/xlsforms/<nombre_xlsform>.xlsx
    form_id: el id_string configurado en la hoja 'settings' de ese XLSForm
             (para este proyecto, coincide con nombre_xlsform).

    Devuelve (creado: bool, resultado) donde `resultado` es lo que devuelve
    upload_koboform() si se creó, o el dict del formulario si ya existía.
    """
    form_existente = buscar_formulario(form_id, api_token, server)

    if form_existente is not None:
        print(f"Formulario '{form_id}' ya existe en Kobo (uid={form_existente['uid']}) — no se toca, solo se subirán datos.")
        return False, form_existente

    print(f"Formulario '{form_id}' no existe todavía — creándolo por primera vez...")
    resultado = upload_koboform(nombre_xlsform, server=server, api_token=api_token, asset_uid=None)

    if isinstance(resultado, str):
        # upload_koboform devuelve un string cuando algo falló
        raise RuntimeError(f"No se pudo crear el formulario '{form_id}': {resultado}")

    print(f"Formulario '{form_id}' creado y desplegado correctamente.")
    return True, resultado


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 3:
        print('Uso: python -m kobo.gestionar_formularios <nombre_form_sin_extension> <api_token> [asset_uid_a_reemplazar]')
        sys.exit(1)

    nombre_form = sys.argv[1]
    token = sys.argv[2]
    uid_previo = sys.argv[3] if len(sys.argv) > 3 else None

    resultado = upload_koboform(nombre_form, api_token=token, asset_uid=uid_previo)
    print(resultado)