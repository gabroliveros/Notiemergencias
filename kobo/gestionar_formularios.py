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

    resultado = upload_koboform('noticias_emergencia_vzla', SERVER, API_TOKEN)
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
    file: nombre del XLSForm sin extensión (ej: 'noticias_emergencia_vzla'),
          debe existir en <raiz_del_repo>/xlsforms/<file>.xlsx
    server: URL base del servidor Kobo, con '/' final.
    api_token: token de la cuenta de KoboToolbox (kf.kobotoolbox.org/token/?format=json).
    asset_uid: si ya existe un formulario desplegado y se quiere reemplazar,
               pasar su UID (se elimina junto con sus respuestas antes de recrear).

    Devuelve (import_url, asset_uid, deploy_ok) en caso de éxito, o un string
    con el mensaje de error en caso de falla.
    """
    kobo_server_url = server
    import_url = None

    nombre = file + '.xlsx'

    # Ruta al XLSForm: <raiz_del_repo>/xlsforms/<file>.xlsx
    basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    kobo_form_xlsx = os.path.join(basedir, 'xlsforms', nombre)

    if not os.path.exists(kobo_form_xlsx):
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
        submissions_resp = requests.get(submissions_url, headers=headers)
        if submissions_resp.status_code == 404:
            asset_uid = None
        elif submissions_resp.status_code != 200:
            return f'Error al obtener respuestas para eliminación: {submissions_resp.status_code} - {submissions_resp.text}'

        if asset_uid:
            results = submissions_resp.json().get('results', [])
            submission_ids = [item['_id'] for item in results]

            if submission_ids:
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

    # 1. CARGAR EL FORMULARIO
    kpi_url = f'{kobo_server_url}imports/'
    attempts = 0
    success = False
    response = None
    try:
        while attempts < max_attempts and not success:
            try:
                with open(kobo_form_xlsx, 'rb') as form:
                    data = {'library': 'false'}
                    response = requests.post(kpi_url, data=data, files={'file': form}, headers=headers)
                    success = response.ok
            except requests.exceptions.RequestException as e:
                if response is not None:
                    response.encoding = 'utf-8'
                    print('Error al cargar el formulario después de', max_attempts, 'intentos:', response.status_code, response.text)
                    return response.text
                else:
                    print(f'Error en la solicitud: {e}')
            attempts += 1
    except Exception:
        try:
            print('Error al cargar el formulario después de', max_attempts, 'intentos:', response.status_code, response.text)
            return response.text
        except Exception:
            mensaje = f'Error al cargar el formulario después de {max_attempts} intentos: la dirección electrónica suministrada no arrojó ninguna respuesta.'
            print(mensaje)
            return mensaje

    # 2. OBTENER EL UID DEL ASSET (formulario)
    if asset_uid in [None, 'None', '']:
        d_content = response.json()
        import_url = d_content['url']
        asset_uid = ''
        count = 0
        try:
            while True:
                if count <= 2:
                    try:
                        import_response = requests.get(import_url, headers=headers)
                        import_data = import_response.json()
                        if import_data['status'] == 'complete':
                            asset_uid = import_data['messages']['created'][0]['uid']
                            break
                        time.sleep(5)
                        count += 1
                    except Exception:
                        time.sleep(5)
                        count += 1
                else:
                    print('No se pudo obtener el UID del formulario.')
                    return (import_url,)
        except Exception:
            print(f'Se cargó el formulario, pero no se pudo obtener el UID después de {count} intentos.')
            return (import_url,)

    # 3. DESPLEGAR EL ASSET (formulario)
    conteo = 0
    while True:
        if conteo <= 2:
            try:
                deploy_url = f'{kobo_server_url}api/v2/assets/{asset_uid}/deployment/'
                deploy_data = {'active': 'true'}
                deploy_response = requests.post(deploy_url, headers=headers, data=deploy_data)

                if deploy_response.status_code == 200:
                    return (import_url, asset_uid, True)
                else:
                    deploy_response.encoding = 'utf-8'
                    print(f'Error {deploy_response.status_code} de KoboToolbox al desplegar: {deploy_response.text}')
                    time.sleep(5)
                    conteo += 1
                    if conteo == max_attempts:
                        return f'No se ha podido desplegar el formulario. Último error: {deploy_response.text}'
            except Exception as e:
                print(f'Error crítico al intentar desplegar el XLSForm en KoboToolbox: {e}')
                time.sleep(3)
                conteo += 1
        else:
            print(f'Se cargó el formulario y se obtuvo el UID, pero no se pudo desplegar después de {conteo} intentos.')
            return (import_url, asset_uid)


# --------------------------------------------------------------------------
# ENVÍO DE DATOS (submissions)
# --------------------------------------------------------------------------
# El hallazgo clave: en el servidor global, las submissions NO se envían a
# kf.kobotoolbox.org sino a su servidor gemelo kc.kobotoolbox.org (arquitectura
# legacy "KoBoCAT" que Kobo mantiene activa para el protocolo OpenRosa),
# usando el mismo token.

import uuid as _uuid_module
import xml.etree.ElementTree as ET


def _servidor_openrosa(server=SERVER_DEFAULT):
    """Convierte la URL del servidor 'kf' al servidor 'kc' que atiende submissions."""
    return server.replace('kf.kobotoolbox.org', 'kc.kobotoolbox.org').replace('eu.kobotoolbox.org', 'kc-eu.kobotoolbox.org')


def obtener_formhub_uuid(form_id, api_token, server=SERVER_DEFAULT):
    """Busca, entre los formularios desplegados del usuario, el que tiene
    id_string == form_id, y devuelve su 'formhub uuid' (necesario para
    construir el XML de cada submission)."""
    import requests

    server_openrosa = _servidor_openrosa(server)
    headers = {'Authorization': f'Token {api_token}', 'Accept': 'application/json'}
    resp = requests.get(f'{server_openrosa}api/v1/forms', headers=headers)
    resp.raise_for_status()

    for form in resp.json():
        if form.get('id_string') == form_id:
            return form['uuid']

    raise ValueError(
        f"No se encontró un formulario desplegado con id_string='{form_id}' en "
        f'{server_openrosa}api/v1/forms. ¿Ya lo desplegaste con upload_koboform()?'
    )


def _construir_xml_submission(form_id, formhub_uuid, campos):
    """Arma el XML de una submission en el formato OpenRosa/KoBoCAT. Usa
    ElementTree (no concatenación de strings) para escapar bien caracteres
    como '&' en URLs, que de otra forma romperían el XML."""
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


def enviar_submission(form_id, campos, api_token, formhub_uuid=None, server=SERVER_DEFAULT):
    """
    Envía UNA submission (una fila de datos) al formulario `form_id`.
    `campos` es un dict {nombre_de_campo_xlsform: valor}. Los campos
    select_one deben venir ya con el 'name' del choice (no el label) —
    ver kobo.xlsform_builder._nombre_choice para generar el mismo formato.
    """
    import requests

    server_openrosa = _servidor_openrosa(server)
    if formhub_uuid is None:
        formhub_uuid = obtener_formhub_uuid(form_id, api_token, server)

    xml_str = _construir_xml_submission(form_id, formhub_uuid, campos)
    headers = {'Authorization': f'Token {api_token}'}
    files = {'xml_submission_file': ('submission.xml', xml_str.encode('utf-8'), 'text/xml')}

    return requests.post(f'{server_openrosa}api/v1/submissions', headers=headers, files=files)


def enviar_filas(form_id, filas, api_token, server=SERVER_DEFAULT, pausa_segundos=0.3):
    """
    Envía varias filas (lista de dicts, ya preparadas con los nombres exactos
    de campo/choice del XLSForm) al formulario `form_id`.
    Devuelve la lista de errores: [(indice, status_code, texto), ...] (vacía si todo OK).
    """
    formhub_uuid = obtener_formhub_uuid(form_id, api_token, server)

    errores = []
    for i, campos in enumerate(filas):
        resp = enviar_submission(form_id, campos, api_token, formhub_uuid=formhub_uuid, server=server)
        if resp.status_code not in (200, 201):
            errores.append((i, resp.status_code, resp.text))
        time.sleep(pausa_segundos)  # evitar saturar el servidor

    print(f'Enviadas {len(filas) - len(errores)} de {len(filas)} filas a "{form_id}". Errores: {len(errores)}')
    return errores


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