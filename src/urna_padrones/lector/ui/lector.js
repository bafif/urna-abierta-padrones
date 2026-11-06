// The screens of the roll reader: one question per screen, and nothing leaves this computer.
(() => {
  const STRINGS = {
    es: {
      'language': 'Read this in English',
      'brand': 'Lector de padrones',
      'rail.pick': 'Elegir el padrón',
      'rail.pick.when': 'El PDF o la foto',
      'rail.read': 'Leerlo',
      'rail.read.when': 'Lo hace la computadora',
      'rail.review': 'Revisar',
      'rail.review.when': 'Lo que no quedó claro',
      'rail.save': 'Guardar',
      'rail.save.when': 'El archivo para la app',
      'rail.here': 'Estás acá',
      'rail.done': 'Hecho',
      'step': 'Paso {n} de 4',
      'pick.title': '¿Qué padrón leemos?',
      'pick.text': 'Elegí el PDF o la foto del padrón.',
      'pick.drop': 'Arrastrá el archivo acá',
      'pick.drop.text': 'o tocá para buscarlo en la computadora.',
      'pick.opening': 'Abriendo el archivo…',
      'pick.private': 'Es privado: el archivo no sale de esta computadora.',
      'pick.choose': 'Elegir el archivo',
      'pick.cancelled': 'Cancelaste la lectura. Podés elegir el mismo archivo u otro.',
      'error.not_pdf': 'Ese archivo no es un PDF ni una foto. Elegí el PDF o la foto del padrón: un JPG, PNG o TIFF.',
      'error.encrypted': 'El PDF tiene contraseña. Abrilo, guardalo sin contraseña y probá de nuevo.',
      'error.damaged': 'El archivo está dañado y no se puede abrir. Probá con otra copia.',
      'error.too_many_pixels': 'La imagen es demasiado grande para abrirla: puede tener hasta 120 millones de píxeles. Achicala, o escaneá la hoja a 300 dpi.',
      'error.empty': 'El PDF no tiene páginas.',
      'error.too_large': 'El archivo es demasiado grande: puede tener hasta 512 MB.',
      'error.incomplete': 'El archivo no llegó entero. Probá de nuevo.',
      'error.unknown_layout': 'El lector entiende padrones hechos como una tabla con líneas, o un PDF con texto, con un encabezado que nombre las columnas, como «Apellido y nombre» y «DNI». También los de la facultad. En este archivo no encontró ninguno.',
      'error.unknown_layout.csv': 'Si tenés el padrón en una planilla de Excel o CSV, subila directo en la app, con «Subir el padrón».',
      'error.internal': 'Algo falló al leer el padrón. Probá de nuevo y, si vuelve a pasar, con otra copia del archivo.',
      'reading.title': 'Leyendo el padrón',
      'reading.text': 'Tarda unos segundos por página. Podés hacer otra cosa, pero no cierres esta ventana.',
      'reading.page': 'Página {n} de {total}',
      'reading.starting': 'Empezando…',
      'reading.people': 'Personas encontradas',
      'reading.left': 'Falta',
      'reading.left.unknown': 'Calculando…',
      'reading.left.little': 'Menos de un minuto',
      'reading.left.one': 'Un minuto, más o menos',
      'reading.left.many': 'Unos {n} minutos',
      'reading.cancel': 'Cancelar',
      'reading.cancelling': 'Cancelando…',
      'failed.title': 'No se pudo leer este archivo',
      'failed.again': 'Probar con otro archivo',
      'summary.title': 'Revisá lo que no quedó claro',
      'summary.text': 'Ya está leído. Algunas filas conviene mirarlas con la imagen al lado.',
      'summary.text.none': 'Ya está leído, y todo quedó claro.',
      'summary.people': 'Personas leídas',
      'summary.doubtful': 'Para mirar',
      'summary.noTable': 'Estas páginas no tenían una tabla y no se leyeron: {pages}.',
      'summary.noTable.one': 'La página {pages} no tenía una tabla y no se leyó.',
      'summary.start': 'Empezar a revisar',
      'summary.continue': 'Seguir revisando',
      'summary.next': 'Seguir',
      'review.later': 'Las reviso después en la app',
      'review.counter': '{n} de {total}',
      'review.page': 'Página {n}',
      'review.image': 'La fila tal como está en el original',
      'review.noImage': 'No hay imagen de esta fila.',
      'review.ok': 'Está bien',
      'review.save': 'Guardar cambio',
      'review.stillWrong': 'Hay datos que no tienen la forma esperada. Corregilos, o tocá «Está bien» para dejarlos así.',
      'review.unsure': 'No se leyó con seguridad: comparalo con la imagen.',
      'review.repaired': 'Le agregamos la barra: fijate que esté bien.',
      'field.name': 'Apellido y nombre',
      'field.document': 'DNI',
      'field.order': 'Número de orden',
      'field.file_number': 'Legajo',
      'field.program': 'Carrera',
      'field.status': 'Estado',
      'why.name': 'Tiene que ser «Apellido, Nombre», sin números.',
      'why.document': 'Tienen que ser 7 u 8 números, sin puntos.',
      'why.order': 'Tiene que ser un número.',
      'why.file_number': 'Tiene que ser como A-1234/3, o quedar vacío.',
      'why.file_number_check': 'El número después de la barra no corresponde a los otros cuatro: revisalos con la imagen.',
      'why.program': 'Falta la carrera.',
      'why.status': 'Tiene que ser A o P.',
      'save.title': 'Guardá el padrón',
      'save.text': 'Queda un archivo para subir a Urna Abierta.',
      'save.name': 'Nombre del padrón',
      'save.button': 'Guardar el archivo',
      'save.saved': 'Listo: el navegador lo mandó a tu carpeta de descargas. Si no lo ves ahí, tocá «Guardar el archivo» de nuevo.',
      'save.failed': 'No se pudo armar el archivo. Probá de nuevo.',
      'save.pending': '{n} personas quedan para revisar en la app: ahí aparecen como pendientes.',
      'save.pending.one': 'Una persona queda para revisar en la app: ahí aparece como pendiente.',
      'save.next': 'Después',
      'save.next1': 'Abrí Urna Abierta.',
      'save.next2': 'Entrá a la elección.',
      'save.next3': 'Tocá «Subir el padrón» y elegí este archivo.',
      'save.private': 'El archivo tiene datos de personas: cuando ya esté subido a la app, borralo de esta computadora.',
      'save.another': 'Leer otro padrón',
      'save.close': 'Cerrar el lector',
      'closed.title': 'Listo, ya podés cerrar esta ventana',
      'closed.text': 'El lector se cerró y borró la copia del archivo.',
      'lost.title': 'El lector está cerrado',
      'lost.text': 'Se cerró su ventana, o pasó mucho tiempo sin usarlo. Para seguir, abrilo de nuevo.',
    },
    en: {
      'language': 'Leer en castellano',
      'brand': 'Roll reader',
      'rail.pick': 'Choose the roll',
      'rail.pick.when': 'The PDF or the photo',
      'rail.read': 'Read it',
      'rail.read.when': 'The computer does it',
      'rail.review': 'Review',
      'rail.review.when': 'What was not clear',
      'rail.save': 'Save',
      'rail.save.when': 'The file for the app',
      'rail.here': 'You are here',
      'rail.done': 'Done',
      'step': 'Step {n} of 4',
      'pick.title': 'Which roll should we read?',
      'pick.text': 'Choose the PDF or the photo of the roll.',
      'pick.drop': 'Drag the file here',
      'pick.drop.text': 'or tap to find it on this computer.',
      'pick.opening': 'Opening the file…',
      'pick.private': 'It stays private: the file never leaves this computer.',
      'pick.choose': 'Choose the file',
      'pick.cancelled': 'You cancelled the reading. You can choose the same file or another one.',
      'error.not_pdf': 'That file is not a PDF or a photo. Choose the PDF or the photo of the roll: a JPG, PNG or TIFF.',
      'error.encrypted': 'The PDF has a password. Open it, save it without a password and try again.',
      'error.damaged': 'The file is damaged and cannot be opened. Try another copy.',
      'error.too_many_pixels': 'The picture is too large to open: it can have up to 120 million pixels. Make it smaller, or scan the page at 300 dpi.',
      'error.empty': 'The PDF has no pages.',
      'error.too_large': 'The file is too large: it can be up to 512 MB.',
      'error.incomplete': 'Only part of the file arrived. Try again.',
      'error.unknown_layout': 'The reader understands rolls laid out as a ruled table, or a PDF with text, with a header that names the columns, such as «Apellido y nombre» and «DNI». Also the university ones. It found none in this file.',
      'error.unknown_layout.csv': 'If you have the roll in an Excel or CSV spreadsheet, upload it straight into the app with “Upload the roll”.',
      'error.internal': 'Something failed while reading the roll. Try again and, if it happens again, with another copy of the file.',
      'reading.title': 'Reading the roll',
      'reading.text': 'It takes a few seconds per page. You can do something else in the meantime, but keep this window open.',
      'reading.page': 'Page {n} of {total}',
      'reading.starting': 'Starting…',
      'reading.people': 'People found',
      'reading.left': 'Time left',
      'reading.left.unknown': 'Working it out…',
      'reading.left.little': 'Less than a minute',
      'reading.left.one': 'About a minute',
      'reading.left.many': 'About {n} minutes',
      'reading.cancel': 'Cancel',
      'reading.cancelling': 'Cancelling…',
      'failed.title': 'This file could not be read',
      'failed.again': 'Try another file',
      'summary.title': 'Review what was not clear',
      'summary.text': 'Reading finished. Some rows are worth checking against their image.',
      'summary.text.none': 'Reading finished, and everything was clear.',
      'summary.people': 'People read',
      'summary.doubtful': 'To check',
      'summary.noTable': 'These pages had no table and were not read: {pages}.',
      'summary.noTable.one': 'Page {pages} had no table and was not read.',
      'summary.start': 'Start reviewing',
      'summary.continue': 'Keep reviewing',
      'summary.next': 'Continue',
      'review.later': 'I’ll review them later in the app',
      'review.counter': '{n} of {total}',
      'review.page': 'Page {n}',
      'review.image': 'The row as it is in the original',
      'review.noImage': 'There is no image of this row.',
      'review.ok': 'Looks right',
      'review.save': 'Save change',
      'review.stillWrong': 'Some values do not look as expected. Fix them, or tap “Looks right” to keep them as they are.',
      'review.unsure': 'The reader was not sure about this one: compare it with the image.',
      'review.repaired': 'We added the slash: check that it is right.',
      'field.name': 'Surname and name',
      'field.document': 'ID number (DNI)',
      'field.order': 'Order number',
      'field.file_number': 'Student number',
      'field.program': 'Degree',
      'field.status': 'Status',
      'why.name': 'It has to be “Surname, Name”, without numbers.',
      'why.document': 'It has to be 7 or 8 digits, without dots.',
      'why.order': 'It has to be a number.',
      'why.file_number': 'It has to look like A-1234/3, or be empty.',
      'why.file_number_check': 'The digit after the slash does not match the other four: check them against the picture.',
      'why.program': 'The degree is missing.',
      'why.status': 'It has to be A or P.',
      'save.title': 'Save the roll',
      'save.text': 'You get a file to upload to Urna Abierta.',
      'save.name': 'Name of the roll',
      'save.button': 'Save the file',
      'save.saved': 'Done: your browser sent it to your downloads folder. If it is not there, tap “Save the file” again.',
      'save.failed': 'The file could not be made. Try again.',
      'save.pending': '{n} people still need reviewing in the app, where they show as pending.',
      'save.pending.one': 'One person still needs reviewing in the app, where they show as pending.',
      'save.next': 'Next',
      'save.next1': 'Open Urna Abierta.',
      'save.next2': 'Go into the election.',
      'save.next3': 'Tap “Upload the roll” and choose this file.',
      'save.private': 'The file has people’s data: once it is uploaded to the app, delete it from this computer.',
      'save.another': 'Read another roll',
      'save.close': 'Close the reader',
      'closed.title': 'Done, you can close this window',
      'closed.text': 'The reader closed and deleted its copy of the file.',
      'lost.title': 'The reader is closed',
      'lost.text': 'Its window was closed, or it was not used for a long time. To continue, open it again.',
    },
  };

  const MAX_PDF = 512 * 1024 * 1024;
  // A PDF, or a picture of the roll: what kind it is, the reader tells from its first bytes.
  const READABLE = /\.(pdf|jpe?g|png|tiff?)$/i;
  const READABLE_TYPES = ['application/pdf', 'image/jpeg', 'image/png', 'image/tiff'];
  const ACCEPTED = ['.pdf', '.jpg', '.jpeg', '.png', '.tif', '.tiff', ...READABLE_TYPES].join(',');
  // The fields in the order a person reads a row, and how wide each one is on a grid of six.
  const FIELDS = [['name', 4], ['order', 2], ['document', 2], ['file_number', 2], ['status', 2], ['program', 6]];
  const LOGO = '<svg viewBox="0 0 48 48" aria-hidden="true"><path d="M7 15v21a6 6 0 006 6h22a6 6 0 006-6V15" fill="none" stroke="currentColor" stroke-width="6" stroke-linecap="round"/><rect x="17" y="4" width="14" height="22" rx="2" fill="currentColor" transform="rotate(8 24 15)"/></svg>';
  const ICONS = {
    flecha: '<path d="M5 12h13M12 6l6 6-6 6"/>',
    tilde: '<path d="M5 12.5l4.5 4.5L19 7"/>',
    candado: '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V8a4 4 0 018 0v3"/>',
    hoja: '<path d="M14 3H7a2 2 0 00-2 2v14a2 2 0 002 2h10a2 2 0 002-2V8z"/><path d="M14 3v5h5M12 17v-6M9 14l3-3 3 3"/>',
    bajar: '<path d="M12 4v11M7 10l5 5 5-5M5 20h14"/>',
  };
  const icon = (name) => `<svg class="ic" viewBox="0 0 24 24" aria-hidden="true">${ICONS[name]}</svg>`;

  const scheme = matchMedia('(prefers-color-scheme: dark)');
  const state = {
    language: 'es',
    screen: 'pick',
    mode: scheme.matches ? 'oscuro' : 'claro',
    problem: '',
    notice: '',
    busy: false,
    progress: null,
    summary: null,
    rows: [],
    at: 0,
    draft: {},
    title: '',
    saved: false,
  };

  const t = (key, values = {}) => (STRINGS[state.language][key] ?? key).replace(/\{(\w+)\}/g, (_, name) => values[name] ?? '');
  const escape = (text) => String(text ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
  const tema = () => window.TEMAS.find((item) => item.id === 'aula') ?? window.TEMAS[0];

  /** Every call to the reader. If it does not answer, it was closed. */
  async function call(path, options) {
    let response;
    try {
      response = await fetch(`api/${path}`, options);
    } catch {
      lost();
      throw new Error('closed');
    }
    return { status: response.status, body: await response.json().catch(() => ({})) };
  }
  const post = (path, body) => call(path, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body ?? {}) });

  function rail() {
    const steps = ['pick', 'read', 'review', 'save'];
    const order = { pick: 0, reading: 1, failed: 1, summary: 2, review: 2, save: 3, closed: 4, lost: -1 };
    const now = order[state.screen];
    return `<aside class="riel"><div class="marca-app">${LOGO}<span>Urna Abierta<small>${t('brand')}</small></span></div>
      <ol class="plan">${steps.map((key, index) => {
        const status = index < now ? 'hecho' : index === now ? 'ahora' : '';
        const when = status === 'ahora' ? t('rail.here') : status === 'hecho' ? t('rail.done') : t(`rail.${key}.when`);
        return `<li class="estacion ${status}"><span class="punto">${status === 'hecho' ? icon('tilde') : ''}</span><div><strong>${t(`rail.${key}`)}</strong><span class="cuando">${when}</span></div></li>`;
      }).join('')}</ol>
      <button class="enlace idioma" data-action="language" lang="${state.language === 'es' ? 'en' : 'es'}">${t('language')}</button></aside>`;
  }

  const button = (kind, label, action, { disabled = false, iconName = '', testid = '' } = {}) =>
    `<button class="${kind}" data-action="${action}" ${disabled ? 'disabled' : ''} ${testid ? `data-testid="${testid}"` : ''}>${iconName ? icon(iconName) : ''}<span>${label}</span></button>`;

  function readingNumbers() {
    const p = state.progress ?? { pages_done: 0, pages_total: 0, rows_found: 0 };
    const share = p.pages_total ? Math.round((100 * p.pages_done) / p.pages_total) : 0;
    const page = p.pages_total ? t('reading.page', { n: Math.min(p.pages_total, p.pages_done + 1), total: p.pages_total }) : t('reading.starting');
    return { p, share, page };
  }

  /** While reading, only the numbers change: the buttons stay, and so does the keyboard focus. */
  function updateReading() {
    const bar = document.querySelector('[data-screen="reading"] .barra');
    if (!bar) return render();
    const { p, share, page } = readingNumbers();
    bar.setAttribute('aria-valuenow', share);
    bar.setAttribute('aria-label', page);
    bar.querySelector('[data-testid="page"]').textContent = page;
    bar.querySelector('b').textContent = `${share} %`;
    bar.querySelector('i').style.setProperty('--v', `${share}%`);
    document.querySelector('[data-testid="rows-found"]').textContent = p.rows_found;
    document.querySelector('.falta-tiempo').textContent = timeLeft(p.eta_seconds);
  }

  function timeLeft(seconds) {
    if (seconds == null) return t('reading.left.unknown');
    if (seconds < 60) return t('reading.left.little');
    const minutes = Math.round(seconds / 60);
    return minutes === 1 ? t('reading.left.one') : t('reading.left.many', { n: minutes });
  }

  function reviewBody(row) {
    const image = `api/rows/${row.index}/image`;
    const picture = row.image
      ? `<div class="imagen-fila" role="img" aria-label="${t('review.image')}" data-testid="row-image">
          <div class="recorte"><img src="${image}" alt=""></div><div class="recorte derecha"><img src="${image}" alt=""></div></div>`
      : `<p class="aclara">${t('review.noImage')}</p>`;
    const fields = FIELDS.map(([name, span]) => {
      const wrong = !row.valid[name];
      // A legajo with the right shape that is still wrong has a check digit that does not add up.
      const why = name === 'file_number' && /^[A-Z]-\d{4}\/\d$/.test(String(row.values[name] ?? '')) ? 'why.file_number_check' : `why.${name}`;
      const hint = wrong ? t(why) : row.unsure.includes(name) ? t('review.unsure') : name === 'file_number' && row.repaired ? t('review.repaired') : '';
      return `<label class="campo ancho-${span} ${wrong ? 'mal' : hint ? 'dudoso' : ''}"><span>${t(`field.${name}`)}</span>
        <input data-field="${name}" type="text" autocomplete="off" spellcheck="false" value="${escape(state.draft[name] ?? row.values[name])}" ${wrong ? 'aria-invalid="true"' : ''} ${hint ? `aria-describedby="motivo-${name}"` : ''}>
        ${hint ? `<small class="motivo" id="motivo-${name}">${hint}</small>` : ''}</label>`;
    }).join('');
    return `${picture}<div class="ficha">${fields}</div>`;
  }

  const changed = () => {
    const row = state.rows[state.at];
    return Boolean(row) && Object.entries(state.draft).some(([name, value]) => value.trim() !== (row.values[name] ?? ''));
  };

  const SCREENS = {
    pick: () => ({
      eyebrow: t('step', { n: 1 }), title: t('pick.title'), text: t('pick.text'),
      body: `<label class="soltar grande ${state.busy ? 'ocupada' : ''}" data-testid="dropzone">
          <input class="oculto" type="file" accept="${ACCEPTED}" data-testid="pdf-file" ${state.busy ? 'disabled' : ''}>
          ${icon('hoja')}<strong>${state.busy ? t('pick.opening') : t('pick.drop')}</strong>${state.busy ? '' : t('pick.drop.text')}
        </label>
        <p class="aclara privado">${icon('candado')}<span>${t('pick.private')}</span></p>
        ${state.notice ? `<p class="estado" role="status">${t(state.notice)}</p>` : ''}`,
      footer: `<button class="boton primario" data-action="choose" ${state.busy ? 'disabled' : ''}>${icon('flecha')}<span>${t('pick.choose')}</span></button>`,
    }),
    reading: () => {
      const { p, share, page } = readingNumbers();
      return {
        eyebrow: t('step', { n: 2 }), title: t('reading.title'), text: t('reading.text'),
        body: `<div class="barra grande" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${share}" aria-label="${escape(page)}">
            <span data-testid="page">${page}</span><b>${share} %</b><i style="--v:${share}%"></i></div>
          <div class="dos-datos"><div><span class="cuando">${t('reading.people')}</span><span class="cifra" data-testid="rows-found">${p.rows_found}</span></div>
            <div><span class="cuando">${t('reading.left')}</span><strong class="falta-tiempo">${timeLeft(p.eta_seconds)}</strong></div></div>`,
        footer: button('boton secundario', state.busy ? t('reading.cancelling') : t('reading.cancel'), 'cancel', { disabled: state.busy }),
      };
    },
    failed: () => ({
      eyebrow: t('step', { n: 2 }), title: t('failed.title'),
      body: `<p class="problema" role="alert" data-testid="read-problem">${t(`error.${state.problem}`)}</p>
        ${state.problem === 'unknown_layout' ? `<div class="tarjeta"><span>${t('error.unknown_layout.csv')}</span></div>` : ''}`,
      footer: button('boton primario', t('failed.again'), 'another', { iconName: 'flecha' }),
      keepProblem: true,
    }),
    summary: () => {
      const s = state.summary;
      const reviewed = state.rows.filter((row) => row.reviewed).length;
      const pages = s.pages_without_table;
      return {
        eyebrow: t('step', { n: 3 }), title: t('summary.title'), text: t(s.doubtful ? 'summary.text' : 'summary.text.none'),
        body: `<div class="dos-datos"><div><span class="cuando">${t('summary.people')}</span><span class="cifra" data-testid="people">${s.people}</span></div>
            <div><span class="cuando">${t('summary.doubtful')}</span><span class="cifra" data-testid="doubtful">${s.doubtful - reviewed}</span></div></div>
          ${pages.length ? `<p class="estado" data-testid="no-table">${t(pages.length === 1 ? 'summary.noTable.one' : 'summary.noTable', { pages: pages.join(', ') })}</p>` : ''}`,
        footer: s.doubtful > reviewed
          ? `<button class="enlace" data-action="later">${t('review.later')}</button>${button('boton primario', t(reviewed ? 'summary.continue' : 'summary.start'), 'review', { iconName: 'flecha' })}`
          : button('boton primario', t('summary.next'), 'later', { iconName: 'flecha' }),
      };
    },
    review: () => {
      const row = state.rows[state.at];
      return {
        eyebrow: `<span data-testid="counter">${t('review.counter', { n: state.at + 1, total: state.rows.length })}</span> · ${t('review.page', { n: row.page })}`,
        title: t('summary.title'), wide: true,
        body: reviewBody(row),
        footer: `<button class="enlace" data-action="later">${t('review.later')}</button>
          ${button('boton secundario', t('review.save'), 'saveRow', { disabled: !changed() || state.busy, testid: 'save-row' })}
          ${button('boton primario', t('review.ok'), 'okRow', { disabled: state.busy, iconName: 'tilde', testid: 'ok-row' })}`,
      };
    },
    save: () => {
      const pending = state.summary?.to_review ?? 0;
      return {
        eyebrow: t('step', { n: 4 }), title: t('save.title'), text: t('save.text'),
        body: `<label class="campo"><span>${t('save.name')}</span><input data-field="title" type="text" autocomplete="off" maxlength="200" value="${escape(state.title)}"></label>
          ${state.saved ? `<p class="resultado bien" role="status" data-testid="saved">${icon('tilde')}${t('save.saved')}</p>` : ''}
          ${pending ? `<p class="estado" data-testid="pending">${pending === 1 ? t('save.pending.one') : t('save.pending', { n: pending })}</p>` : ''}
          <div class="tarjeta pasos"><strong>${t('save.next')}</strong><ol><li>${t('save.next1')}</li><li>${t('save.next2')}</li><li>${t('save.next3')}</li></ol></div>
          <p class="aclara privado">${icon('candado')}<span>${t('save.private')}</span></p>`,
        footer: `<button class="enlace" data-action="another">${t('save.another')}</button>
          ${button('boton secundario', t('save.close'), 'quit')}
          ${button('boton primario', t('save.button'), 'download', { iconName: 'bajar', testid: 'download', disabled: state.busy })}`,
      };
    },
    closed: () => ({ title: t('closed.title'), text: t('closed.text'), body: '' }),
    lost: () => ({ title: t('lost.title'), text: t('lost.text'), body: '' }),
  };

  let renderedScreen = '';

  function render() {
    const screen = SCREENS[state.screen]();
    const theme = tema();
    const recipes = Object.entries(window.URNA_TEMA.recetas(theme)).map(([k, v]) => `${k}="${v}"`).join(' ');
    document.documentElement.lang = state.language;
    const focused = document.activeElement?.dataset?.field;
    const focusedAction = state.screen === renderedScreen ? document.activeElement?.dataset?.action : undefined;
    renderedScreen = state.screen;
    const problem = state.problem && !screen.keepProblem ? `<p class="problema" role="alert" data-testid="problem">${escape(state.problem)}</p>` : '';
    document.getElementById('app').innerHTML = `
      <div class="ventana" ${recipes} style="${window.URNA_TEMA.variables(theme, state.mode, 'plan').replaceAll('"', '&quot;')}">
        ${rail()}
        <section class="ventana-derecha ${screen.wide ? 'ancha' : ''}" data-screen="${state.screen}">
          ${screen.eyebrow ? `<p class="ojo">${screen.eyebrow}</p>` : ''}
          <h1 class="t1">${screen.title}</h1>
          ${screen.text ? `<p class="bajada">${screen.text}</p>` : ''}
          <div class="cuerpo-v">${screen.body}${problem}</div>
          ${screen.footer ? `<div class="pie-v">${screen.footer}</div>` : ''}
        </section>
      </div>`;
    if (focused) document.querySelector(`[data-field="${focused}"]`)?.focus();
    else if (focusedAction) document.querySelector(`[data-action="${focusedAction}"]:not([disabled])`)?.focus();
  }

  const go = (screen) => {
    state.problem = '';
    state.busy = false;
    state.screen = screen;
    render();
  };

  function lost() {
    state.screen = 'lost';
    state.problem = '';
    render();
  }

  function defaultTitle(name) {
    return String(name ?? '').replace(READABLE, '').replace(/[-_\s]+/g, ' ').trim().slice(0, 200);
  }

  /** Follows the reading until it ends, one look per second. */
  async function follow() {
    const { body } = await call('state');
    state.progress = body;
    if (body.state === 'reading') {
      if (state.screen === 'reading') updateReading();
      setTimeout(() => follow().catch(() => undefined), 1_000);
      return;
    }
    if (body.state === 'done') {
      state.summary = body.summary;
      state.title = defaultTitle(body.name);
      state.rows = (await call('rows?which=doubtful')).body.rows ?? [];
      state.at = 0;
      state.saved = false;
      return go('summary');
    }
    if (body.state === 'failed') {
      state.busy = false;
      state.screen = 'failed';
      state.problem = body.error ?? 'internal';
      return render();
    }
    // Cancelled: the reader already forgot the file.
    state.notice = body.error === 'cancelled' ? 'pick.cancelled' : '';
    go('pick');
  }

  async function loadPdf(file) {
    state.notice = '';
    state.problem = '';
    const readable = READABLE.test(file.name) || READABLE_TYPES.includes(file.type);
    if (!readable) {
      state.problem = t('error.not_pdf');
      return render();
    }
    if (file.size > MAX_PDF) {
      state.problem = t('error.too_large');
      return render();
    }
    state.busy = true;
    render();
    const { status, body } = await call(`pdf?name=${encodeURIComponent(file.name)}`, { method: 'POST', headers: { 'content-type': file.type || 'application/octet-stream' }, body: file });
    state.busy = false;
    if (status !== 200) {
      state.problem = t(`error.${body.error ?? 'internal'}`);
      return render();
    }
    await post('read');
    state.progress = null;
    go('reading');
    follow().catch(() => undefined);
  }

  async function updateSummary() {
    const { body } = await call('state');
    if (body.summary) state.summary = body.summary;
  }

  /** The next row nobody looked at yet, or the last screen. */
  async function nextRow(from) {
    state.draft = {};
    state.problem = '';
    const next = state.rows.findIndex((row, index) => index >= from && !row.reviewed);
    if (next === -1) {
      await updateSummary();
      return go('save');
    }
    state.at = next;
    const after = state.rows[next + 1];
    if (after?.image) new Image().src = `api/rows/${after.index}/image`;
    go('review');
  }

  async function answerRow(path, body) {
    const row = state.rows[state.at];
    state.busy = true;
    render();
    const answer = await post(`rows/${row.index}${path}`, body);
    state.busy = false;
    if (answer.status !== 200) {
      state.problem = t('error.internal');
      return render();
    }
    state.rows[state.at] = answer.body;
    return answer.body;
  }

  const ACTIONS = {
    language: () => {
      state.language = state.language === 'es' ? 'en' : 'es';
      render();
    },
    choose: () => document.querySelector('[data-testid="pdf-file"]')?.click(),
    cancel: async () => {
      state.busy = true;
      render();
      await post('cancel');
    },
    another: async () => {
      await post('reset');
      Object.assign(state, { summary: null, rows: [], at: 0, draft: {}, title: '', saved: false, notice: '' });
      go('pick');
    },
    review: () => nextRow(0),
    later: async () => {
      await updateSummary();
      go('save');
    },
    // «Está bien» keeps what was typed too: the person says the row is right as it is on screen.
    okRow: async () => {
      const values = changed() ? state.draft : null;
      const row = await answerRow(values ? '' : '/ok', values ? { values, ok: true } : {});
      if (row) nextRow(state.at + 1);
    },
    // «Guardar cambio» only moves on when every value has its format; otherwise it says why.
    saveRow: async () => {
      if (!changed()) return;
      const row = await answerRow('', { values: state.draft });
      if (!row) return;
      state.draft = {};
      if (row.reviewed) return nextRow(state.at + 1);
      state.problem = t('review.stillWrong');
      render();
    },
    // The file is fetched first, so «Listo» only shows once it really came.
    download: async () => {
      if (state.busy) return;
      Object.assign(state, { busy: true, saved: false, problem: '' });
      render();
      let response;
      let data;
      try {
        response = await fetch(`api/save?title=${encodeURIComponent(state.title)}`);
        data = response.ok ? await response.blob() : null;
      } catch {
        state.busy = false;
        return lost();
      }
      state.busy = false;
      if (!data) {
        state.problem = t('save.failed');
        return render();
      }
      const name = /filename="([A-Za-z0-9-]+\.padron)"/.exec(response.headers.get('content-disposition') ?? '')?.[1] ?? 'padron.padron';
      const url = URL.createObjectURL(data);
      const link = document.createElement('a');
      link.href = url;
      link.download = name;
      document.body.append(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
      state.saved = true;
      render();
    },
    quit: async () => {
      await post('quit');
      go('closed');
    },
  };

  // Dropping a file anywhere in the window counts, and the browser must not open it instead of the reader.
  const dropzone = () => document.querySelector('[data-testid="dropzone"]');
  document.addEventListener('dragover', (event) => {
    event.preventDefault();
    dropzone()?.classList.add('encima');
  });
  document.addEventListener('dragleave', (event) => {
    if (!event.relatedTarget) dropzone()?.classList.remove('encima');
  });
  document.addEventListener('drop', (event) => {
    event.preventDefault();
    dropzone()?.classList.remove('encima');
    const file = event.dataTransfer?.files?.[0];
    if (file && state.screen === 'pick' && !state.busy) loadPdf(file).catch(() => undefined);
  });
  document.addEventListener('change', (event) => {
    const file = event.target.dataset?.testid === 'pdf-file' ? event.target.files?.[0] : null;
    if (file) loadPdf(file).catch(() => undefined);
  });

  document.addEventListener('input', (event) => {
    const name = event.target.dataset?.field;
    if (!name) return;
    if (name === 'title') {
      state.title = event.target.value;
      return;
    }
    state.draft[name] = event.target.value;
    const save = document.querySelector('[data-testid="save-row"]');
    if (save) save.disabled = !changed() || state.busy;
  });

  // Enter answers the row: it saves what was typed, or says the row is fine.
  document.addEventListener('keydown', (event) => {
    if (event.key !== 'Enter' || event.target.closest?.('button, a, label.soltar') || state.busy) return;
    if (state.screen === 'review') {
      event.preventDefault();
      (changed() ? ACTIONS.saveRow : ACTIONS.okRow)().catch(() => undefined);
    } else if (state.screen === 'save' && event.target.dataset?.field === 'title') {
      event.preventDefault();
      ACTIONS.download().catch(() => undefined);
    }
  });

  document.addEventListener('click', (event) => {
    const target = event.target.closest('button');
    const action = target?.dataset.action;
    if (action && ACTIONS[action]) Promise.resolve(ACTIONS[action]()).catch(() => undefined);
  });

  scheme.addEventListener('change', (event) => {
    state.mode = event.matches ? 'oscuro' : 'claro';
    render();
  });

  // While this window is open the reader stays; once it is closed, the reader ends by itself after a while.
  setInterval(() => {
    if (state.screen !== 'closed' && state.screen !== 'lost') call('state').catch(() => undefined);
  }, 5 * 60 * 1_000);

  render();
})();
