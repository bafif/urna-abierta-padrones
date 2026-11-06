// @ts-nocheck: plain script shared with the design gallery.
// Themes of Urna Abierta. A theme is data: colors for each mode, fonts, shapes, and a few named
// recipes (how a crossed-out name looks, what the background is, what panels are made of).
// A party can write its own by adding one more object like these.
window.TEMAS = window.TEMAS || [];

window.TEMAS.push(
  {
    id: 'aula',
    nombre: 'Aula',
    idea: 'Se vota en escuelas. De día es un cuaderno rayado, con el número en el margen y una línea de lapicera para tachar. De noche es un pizarrón. Es el tema por defecto: la letra está hecha para quien ve poco.',
    fuentes: {
      titulo: "'Atkinson Hyperlegible Next'",
      texto: "'Atkinson Hyperlegible Next'",
      boton: "'Atkinson Hyperlegible Next'",
      numero: "'Atkinson Hyperlegible Next'",
    },
    forma: { radio: '10px', radioBoton: '12px', borde: '2px', pesoTitulo: 800, tituloCaja: 'none', tituloTracking: '-0.015em', tituloAlto: 1.08, escalaTitulo: 1.02, pesoBoton: 700, botonCaja: 'none', botonTracking: '0' },
    recetas: { tachado: 'lapicera', fondo: 'cuaderno', material: 'plano', cabecera: 'simple' },
    claro: {
      fondo: '#FDFEFB', superficie: '#FFFFFF', superficie2: '#EEF4F8', texto: '#14233A', suave: '#46566B', linea: '#C6D9E8', margen: '#E2726E',
      primario: '#1E5A44', sobrePrimario: '#FFFFFF', acento: '#1E5A44', marca: '#1746C7', peligro: '#AE2418', sobrePeligro: '#FFFFFF', peligroFondo: '#FCE9E6', peligroTexto: '#7E170E', bien: '#1E5A44', bienFondo: '#E3F2EA',
    },
    oscuro: {
      fondo: '#14302A', superficie: '#1B3B33', superficie2: '#21463C', texto: '#F3F6EC', suave: '#C2D3C8', linea: '#3A5D52', margen: '#3A5D52',
      primario: '#F5D768', sobrePrimario: '#16261F', acento: '#F5D768', marca: '#FFFDF2', peligro: '#FFB4A6', sobrePeligro: '#3A0B05', peligroFondo: '#3F2622', peligroTexto: '#FFD6CE', bien: '#A9E4C4', bienFondo: '#21463C',
    },
  },
  {
    id: 'vidrio',
    nombre: 'Vidrio',
    idea: 'Vidrio líquido sobre el celeste y blanco: paneles que dejan pasar la luz, con el texto siempre sobre una capa lo bastante opaca para leerse. Es el más vistoso, y también el que más le pide a un teléfono barato.',
    fuentes: { titulo: "'Onest Variable'", texto: "'Onest Variable'", boton: "'Onest Variable'", numero: "'Onest Variable'" },
    forma: { radio: '26px', radioBoton: '999px', borde: '1px', pesoTitulo: 700, tituloCaja: 'none', tituloTracking: '-0.025em', tituloAlto: 1.08, escalaTitulo: 1, pesoBoton: 650, botonCaja: 'none', botonTracking: '-0.005em' },
    recetas: { tachado: 'suave', fondo: 'aurora', material: 'vidrio', cabecera: 'simple' },
    claro: {
      fondo: '#D5E8F6', superficie: '#F7FBFF', superficie2: '#E9F3FB', texto: '#0C2340', suave: '#3C5470', linea: '#B7CFE3', margen: '#B7CFE3',
      primario: '#0B4FB3', sobrePrimario: '#FFFFFF', acento: '#0B4FB3', marca: '#0B4FB3', peligro: '#B3261E', sobrePeligro: '#FFFFFF', peligroFondo: '#FCE8E6', peligroTexto: '#7A1610', bien: '#0B6B4F', bienFondo: '#DDF3EA',
      aurora: ['#8FC7EE', '#FFFFFF', '#B5D8F2', '#6AA8E0'],
    },
    oscuro: {
      fondo: '#071427', superficie: '#16263F', superficie2: '#1E3250', texto: '#F1F6FC', suave: '#B9CAE0', linea: '#34496A', margen: '#34496A',
      primario: '#9CCBFF', sobrePrimario: '#06213F', acento: '#9CCBFF', marca: '#9CCBFF', peligro: '#FFB4AB', sobrePeligro: '#410B06', peligroFondo: '#3D2230', peligroTexto: '#FFD9D4', bien: '#8FE3BF', bienFondo: '#173B3A',
      aurora: ['#114A85', '#0B2A55', '#1E6FA8', '#072044'],
    },
  },
  {
    id: 'feria',
    nombre: 'Feria',
    idea: 'Color para orientarse: cada tarea tiene el suyo, siempre el mismo. Tachar es verde, contar sobres es amarillo, un problema es rojo. Sirve para explicarle a alguien por teléfono: «tocá el verde».',
    fuentes: { titulo: "'Gabarito Variable'", texto: "'Gabarito Variable'", boton: "'Gabarito Variable'", numero: "'Gabarito Variable'" },
    forma: { radio: '20px', radioBoton: '20px', borde: '3px', pesoTitulo: 800, tituloCaja: 'none', tituloTracking: '-0.02em', tituloAlto: 1.02, escalaTitulo: 1.14, pesoBoton: 700, botonCaja: 'none', botonTracking: '0' },
    recetas: { tachado: 'sello', fondo: 'liso', material: 'plano', cabecera: 'banda', decor: 'formas' },
    claro: {
      fondo: '#FFFFFF', superficie: '#F4F2EC', superficie2: '#E9E6DC', texto: '#17140F', suave: '#544F45', linea: '#17140F', margen: '#17140F',
      primario: '#0B6E50', sobrePrimario: '#FFFFFF', acento: '#0B6E50', marca: '#C42A12', peligro: '#C42A12', sobrePeligro: '#FFFFFF', peligroFondo: '#FFE3DC', peligroTexto: '#7E1908', bien: '#0B6E50', bienFondo: '#D9F2E7',
      bandas: {
        plan: ['#1450C9', '#FFFFFF'], tachar: ['#0B6E50', '#FFFFFF'], aviso: ['#C42A12', '#FFFFFF'], sobres: ['#FFC53D', '#17140F'], escrutinio: ['#5A2DBA', '#FFFFFF'],
        partido: ['#1450C9', '#FFFFFF'], equipo: ['#E0468B', '#17140F'], seguridad: ['#17140F', '#FFFFFF'], eleccion: ['#FFC53D', '#17140F'],
      },
    },
    oscuro: {
      fondo: '#15120E', superficie: '#25211A', superficie2: '#332D24', texto: '#FBF8F0', suave: '#CFC9BB', linea: '#FBF8F0', margen: '#FBF8F0',
      primario: '#3FD6A2', sobrePrimario: '#06241A', acento: '#3FD6A2', marca: '#FF8A6E', peligro: '#FF8A6E', sobrePeligro: '#3A0D03', peligroFondo: '#3F1E15', peligroTexto: '#FFD5CA', bien: '#3FD6A2', bienFondo: '#123A2C',
      bandas: {
        plan: ['#7FA8FF', '#07183D'], tachar: ['#3FD6A2', '#06241A'], aviso: ['#FF8A6E', '#3A0D03'], sobres: ['#FFD25E', '#2A1E00'], escrutinio: ['#B79BFF', '#1C0A47'],
        partido: ['#7FA8FF', '#07183D'], equipo: ['#FF8FC0', '#3A0620'], seguridad: ['#FBF8F0', '#15120E'], eleccion: ['#FFD25E', '#2A1E00'],
      },
    },
  },
  {
    id: 'tablero',
    nombre: 'Tablero',
    idea: 'Moderno y sin adornos: el número manda. Letra ancha, ángulos rectos y líneas finas, como un tablero de resultados. Se entiende de un vistazo cuánto falta, incluso a pleno sol.',
    fuentes: { titulo: "'Archivo Variable'", texto: "'Archivo Variable'", boton: "'Archivo Variable'", numero: "'Archivo Variable'" },
    forma: { radio: '0px', radioBoton: '0px', borde: '2px', pesoTitulo: 800, tituloCaja: 'uppercase', tituloTracking: '-0.01em', tituloAlto: 0.98, escalaTitulo: 0.94, pesoBoton: 700, botonCaja: 'uppercase', botonTracking: '0.02em', anchoTitulo: '125%' },
    recetas: { tachado: 'linea', fondo: 'liso', material: 'filete', cabecera: 'simple' },
    claro: {
      fondo: '#FFFFFF', superficie: '#FFFFFF', superficie2: '#F0F0EE', texto: '#0A0A0A', suave: '#4A4A48', linea: '#0A0A0A', margen: '#0A0A0A',
      primario: '#0A0A0A', sobrePrimario: '#FFFFFF', acento: '#D42F06', marca: '#D42F06', peligro: '#D42F06', sobrePeligro: '#FFFFFF', peligroFondo: '#FFE6DF', peligroTexto: '#8A1E03', bien: '#0A0A0A', bienFondo: '#F0F0EE',
    },
    oscuro: {
      fondo: '#0A0A0A', superficie: '#0A0A0A', superficie2: '#1C1C1B', texto: '#FFFFFF', suave: '#BDBDBA', linea: '#FFFFFF', margen: '#FFFFFF',
      primario: '#FFFFFF', sobrePrimario: '#0A0A0A', acento: '#FF6A3D', marca: '#FF6A3D', peligro: '#FF6A3D', sobrePeligro: '#1F0700', peligroFondo: '#341208', peligroTexto: '#FFD5C7', bien: '#FFFFFF', bienFondo: '#1C1C1B',
    },
  },
  {
    id: 'mate',
    nombre: 'Mate',
    idea: 'El más tranquilo: verde yerba, formas redondas y mucho aire, para que nadie se ponga nervioso. Nada se tacha con fuerza: quien ya votó se aparta en silencio, con un tilde. De noche, luz de lámpara.',
    fuentes: { titulo: "'Nunito Variable'", texto: "'Nunito Variable'", boton: "'Nunito Variable'", numero: "'Nunito Variable'" },
    forma: { radio: '28px', radioBoton: '26px', borde: '0px', pesoTitulo: 800, tituloCaja: 'none', tituloTracking: '-0.01em', tituloAlto: 1.12, escalaTitulo: 1, pesoBoton: 800, botonCaja: 'none', botonTracking: '0' },
    recetas: { tachado: 'suave', fondo: 'liso', material: 'almohada', cabecera: 'simple' },
    claro: {
      fondo: '#E8EFE4', superficie: '#F8FAF5', superficie2: '#DDE7D8', texto: '#1E2E24', suave: '#46584B', linea: '#CBD8C5', margen: '#CBD8C5',
      primario: '#2F5D43', sobrePrimario: '#FFFFFF', acento: '#2F5D43', marca: '#2F5D43', peligro: '#A63A24', sobrePeligro: '#FFFFFF', peligroFondo: '#F8E4DC', peligroTexto: '#74230F', bien: '#2F5D43', bienFondo: '#DDEBD9',
    },
    oscuro: {
      fondo: '#1A2420', superficie: '#25322C', superficie2: '#2F3F38', texto: '#F4F1E6', suave: '#C9C8B6', linea: '#3D4F46', margen: '#3D4F46',
      primario: '#F3B65E', sobrePrimario: '#2A1A04', acento: '#F3B65E', marca: '#F3B65E', peligro: '#F7A48F', sobrePeligro: '#3A0F05', peligroFondo: '#43291F', peligroTexto: '#FFDACE', bien: '#A9D8B4', bienFondo: '#2C4136',
    },
  },
);
