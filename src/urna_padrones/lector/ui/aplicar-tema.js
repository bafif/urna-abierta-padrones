// @ts-nocheck: plain script shared with the design gallery.
// Turns a theme's data into CSS variables and recipe attributes. Shared by the app and the design gallery.
(() => {
  function variables(tema, modo, accion) {
    const c = tema[modo];
    const f = tema.forma;
    const v = {
      '--fondo': c.fondo, '--superficie': c.superficie, '--superficie2': c.superficie2, '--texto': c.texto, '--suave': c.suave, '--linea': c.linea, '--margen': c.margen,
      '--primario': c.primario, '--sobre-primario': c.sobrePrimario, '--acento': c.acento, '--marca': c.marca, '--peligro': c.peligro, '--sobre-peligro': c.sobrePeligro,
      '--peligro-fondo': c.peligroFondo, '--peligro-texto': c.peligroTexto, '--bien': c.bien, '--bien-fondo': c.bienFondo,
      '--f-titulo': tema.fuentes.titulo, '--f-texto': tema.fuentes.texto, '--f-boton': tema.fuentes.boton, '--f-numero': tema.fuentes.numero,
      '--radio': f.radio, '--r-boton': f.radioBoton, '--borde': f.borde, '--peso-titulo': f.pesoTitulo, '--caja-titulo': f.tituloCaja, '--tracking-titulo': f.tituloTracking,
      '--alto-titulo': f.tituloAlto, '--escala-titulo': f.escalaTitulo, '--peso-boton': f.pesoBoton, '--caja-boton': f.botonCaja, '--tracking-boton': f.botonTracking,
    };
    v['--ancho-titulo'] = f.anchoTitulo ?? '100%';
    v['--ojo-caja'] = f.ojoCaja ?? 'none';
    v['--ojo-tracking'] = f.ojoTracking ?? '0';
    v['--fondo-pie'] = c.fondoPie ?? 'transparent';
    v['--sobre-pie'] = c.sobrePie ?? c.acento;
    v['--peligro-borde'] = c.peligroBorde ?? c.peligro;
    v['--sombra-banda'] = c.sombraBanda ?? 'transparent';
    if (c.aurora) c.aurora.forEach((color, i) => (v[`--a${i + 1}`] = color));
    if (tema.recetas.material === 'vidrio') {
      const claro = modo === 'claro';
      v['--vidrio-borde'] = claro ? 'rgba(255,255,255,.7)' : 'rgba(255,255,255,.16)';
      v['--vidrio-brillo'] = claro ? 'rgba(255,255,255,.9)' : 'rgba(255,255,255,.22)';
      v['--vidrio-sombra'] = claro ? 'rgba(20,60,110,.16)' : 'rgba(0,0,0,.4)';
    }
    if (tema.recetas.material === 'almohada') v['--almohada'] = modo === 'claro' ? 'rgba(47,74,58,.13)' : 'rgba(0,0,0,.32)';
    const banda = c.bandas && (c.bandas[accion] ?? c.bandas.todas ?? c.bandas.plan);
    v['--ojo-banda'] = c.ojoBanda ?? banda?.[1] ?? 'currentColor';
    if (banda) {
      v['--banda'] = banda[0];
      v['--sobre-banda'] = banda[1];
      if (tema.recetas.decor === 'formas' && accion !== 'plan' && accion !== 'seguridad') {
        v['--primario'] = banda[0];
        v['--sobre-primario'] = banda[1];
      }
    }
    return Object.entries(v).map(([k, val]) => `${k}:${val}`).join(';');
  }

  const recetas = (tema) => {
    const r = tema.recetas;
    return {
      'data-tachado': r.tachado, 'data-fondo': r.fondo, 'data-material': r.material, 'data-cabecera': r.cabecera, 'data-decor': r.decor ?? '',
      'data-sombra-titulo': String(Boolean(r.sombraTitulo)), 'data-pie-banda': String(Boolean(tema.claro.fondoPie)),
    };
  };
  const atributos = (tema) => Object.entries(recetas(tema)).map(([k, val]) => `${k}="${val}"`).join(' ');

  window.URNA_TEMA = { variables, atributos, recetas };
})();
