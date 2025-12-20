const AVAILABLE_LOCALES = {
  en: { label: "English", direction: "ltr", intlLocale: "en-US" },
  es: { label: "Español", direction: "ltr", intlLocale: "es-ES" },
  pseudo: { label: "Pseudo (debug)", direction: "rtl", intlLocale: "en-US" }
};

const translations = {
  en: {
    app: {
      title: "BIOwerk Control Panel",
      tagline: "Manage your Bio-Themed Agentic Office Suite",
      helper: "Monitor launch health, remediation alerts, and keyboard-friendly controls for start, stop, refresh, and restart.",
      skipLink: "Skip to main content",
      statusSummary: "{running} of {total} services running",
      lastChecked: "Last checked at {time}",
      quit: "Quit"
    },
    nav: {
      label: "Primary navigation",
      dashboard: "Dashboard",
      services: "Services",
      logs: "Logs",
      links: "Quick Links",
      settings: "Settings",
      dashboardAria: "Open dashboard",
      servicesAria: "Open services view",
      logsAria: "Open logs view",
      linksAria: "Open quick links",
      settingsAria: "Open settings"
    },
    hero: {
      dockerStatusLabel: "Docker Status",
      dockerStatusChecking: "Checking...",
      dockerDaemonNotRunning: "(Daemon not running)",
      dockerHelper: "Verifies Docker install and daemon readiness across macOS, Windows, and Linux."
    },
    buttons: {
      start: "Start Services",
      stop: "Stop Services",
      restart: "Restart Services",
      refresh: "Refresh Status",
      startAria: "Start BIOwerk services",
      stopAria: "Stop BIOwerk services",
      restartAria: "Restart BIOwerk services",
      refreshAria: "Refresh service health status",
      allLogs: "All Services",
      clearLogs: "Clear Logs",
      openLogs: "Logs",
      openService: "Open",
      applyLocale: "Apply language"
    },
    sections: {
      dashboardTitle: "BIOwerk Control Panel",
      dashboardIntro: "Manage your Bio-Themed Agentic Office Suite",
      dashboardHelper: "Tooltips surface remediation guidance for alerts, metrics, and actions; focus order follows the page layout.",
      servicesTitle: "Services Management",
      servicesHelper: "Focus any card to review status, URLs, and remediation actions with clear labels.",
      logsTitle: "Service Logs",
      logsHelper: "Use keyboard to focus the latest log output; screen readers announce new lines as they stream.",
      linksTitle: "Quick Links",
      linksHelper: "Tooltips describe each dashboard; links open in your default browser.",
      settingsTitle: "Settings",
      statusHeading: "Service Status",
      statusHelper: "Tooltips surface remediation guidance for alerts, metrics, and actions; focus order follows the page layout."
    },
    quickLinks: {
      apiDocs: "API Documentation",
      grafana: "Grafana Dashboard",
      prometheus: "Prometheus",
      osteon: "Osteon Writer",
      myocyte: "Myocyte Analysis",
      synapse: "Synapse Presentation",
      ariaLabel: "Open {name}"
    },
    services: {
      mesh: "Mesh Gateway",
      osteon: "Osteon (Writer)",
      myocyte: "Myocyte (Spreadsheet)",
      synapse: "Synapse (Presentation)",
      circadian: "Circadian (Scheduler)",
      nucleus: "Nucleus (Director)",
      grafana: "Grafana (Monitoring)",
      prometheus: "Prometheus",
      statusLabel: "{name} status {status}",
      cardHelper: "Hover or focus for thresholds; alerts link to remediation guidance in dashboards."
    },
    statuses: {
      running: "Running",
      stopped: "Stopped",
      starting: "Starting"
    },
    alerts: {
      dockerNotInstalled: "Docker is not installed. Please install Docker Desktop.",
      dockerDaemonDown: "Docker daemon is not running. Please start Docker.",
      dockerMissingTitle: "Docker Not Found",
      dockerDialogDetail: "Docker is required to run BIOwerk. Download Docker Desktop to continue.",
      dockerDownload: "Download Docker",
      dialogCancel: "Cancel",
      composeMissingTitle: "Configuration Error",
      composeMissingBody: "docker-compose.yml not found at {path}",
      envCreatedTitle: "Configuration Created",
      envCreatedBody: "A default configuration file has been created",
      envCreatedDetail: "Please review the .env file and restart the application if you need to change any settings.",
      startStarting: "Starting BIOwerk services...",
      startSuccess: "Services started successfully",
      startFailure: "Failed to start services",
      stopStopping: "Stopping BIOwerk services...",
      stopSuccess: "Services stopped successfully",
      stopFailure: "Failed to stop services",
      localeUpdated: "Language updated to {language}"
    },
    docker: {
      installed: "✓ Installed",
      notInstalled: "✗ Not Installed",
      ready: "Docker is ready"
    },
    logs: {
      title: "Service Logs",
      ariaLabel: "Service log output"
    },
    settings: {
      configLabel: "Configuration File",
      openEnv: "Open .env File",
      configHelper: "Edit environment variables, API keys, and service configuration",
      composeLabel: "Docker Compose File",
      composeLocated: "Located at:",
      localeLabel: "Language",
      localeHelper: "Switch languages to validate truncation, RTL layout, and localization coverage."
    }
  },
  es: {
    app: {
      title: "Panel de Control BIOwerk",
      tagline: "Administra tu suite ofimática bio-temática y con agentes",
      helper: "Supervisa el estado de inicio, alertas y controles con teclado para iniciar, detener, actualizar y reiniciar.",
      skipLink: "Saltar al contenido principal",
      statusSummary: "{running} de {total} servicios en ejecución",
      lastChecked: "Última comprobación a las {time}",
      quit: "Salir"
    },
    nav: {
      label: "Navegación principal",
      dashboard: "Tablero",
      services: "Servicios",
      logs: "Registros",
      links: "Enlaces rápidos",
      settings: "Configuración",
      dashboardAria: "Abrir tablero",
      servicesAria: "Abrir vista de servicios",
      logsAria: "Abrir vista de registros",
      linksAria: "Abrir enlaces rápidos",
      settingsAria: "Abrir configuración"
    },
    hero: {
      dockerStatusLabel: "Estado de Docker",
      dockerStatusChecking: "Comprobando...",
      dockerDaemonNotRunning: "(Daemon no iniciado)",
      dockerHelper: "Verifica la instalación de Docker y la disponibilidad del daemon en macOS, Windows y Linux."
    },
    buttons: {
      start: "Iniciar servicios",
      stop: "Detener servicios",
      restart: "Reiniciar servicios",
      refresh: "Actualizar estado",
      startAria: "Iniciar servicios de BIOwerk",
      stopAria: "Detener servicios de BIOwerk",
      restartAria: "Reiniciar servicios de BIOwerk",
      refreshAria: "Actualizar estado de salud de los servicios",
      allLogs: "Todos los servicios",
      clearLogs: "Limpiar registros",
      openLogs: "Registros",
      openService: "Abrir",
      applyLocale: "Aplicar idioma"
    },
    sections: {
      dashboardTitle: "Panel de Control BIOwerk",
      dashboardIntro: "Administra tu suite ofimática bio-temática y con agentes",
      dashboardHelper: "Las descripciones muestran guías de remediación; el orden de enfoque sigue el diseño de la página.",
      servicesTitle: "Gestión de servicios",
      servicesHelper: "Enfoca cualquier tarjeta para revisar el estado, las URL y las acciones con etiquetas claras.",
      logsTitle: "Registros de servicio",
      logsHelper: "Usa el teclado para enfocar la salida más reciente; el lector de pantalla anuncia nuevas líneas.",
      linksTitle: "Enlaces rápidos",
      linksHelper: "Las descripciones explican cada panel; los enlaces se abren en tu navegador predeterminado.",
      settingsTitle: "Configuración",
      statusHeading: "Estado de los servicios",
      statusHelper: "Las descripciones muestran guías de remediación; el orden de enfoque sigue el diseño de la página."
    },
    quickLinks: {
      apiDocs: "Documentación de API",
      grafana: "Panel de Grafana",
      prometheus: "Prometheus",
      osteon: "Osteon Writer",
      myocyte: "Análisis de Myocyte",
      synapse: "Presentación de Synapse",
      ariaLabel: "Abrir {name}"
    },
    services: {
      mesh: "Malla (Gateway)",
      osteon: "Osteon (Redactor)",
      myocyte: "Myocyte (Hoja de cálculo)",
      synapse: "Synapse (Presentación)",
      circadian: "Circadian (Programador)",
      nucleus: "Nucleus (Director)",
      grafana: "Grafana (Monitoreo)",
      prometheus: "Prometheus",
      statusLabel: "Estado de {name}: {status}",
      cardHelper: "Pasa el cursor o enfoca para ver umbrales; las alertas enlazan a guías de remediación."
    },
    statuses: {
      running: "En ejecución",
      stopped: "Detenido",
      starting: "Iniciando"
    },
    alerts: {
      dockerNotInstalled: "Docker no está instalado. Instala Docker Desktop.",
      dockerDaemonDown: "El daemon de Docker no está ejecutándose. Inícialo para continuar.",
      dockerMissingTitle: "Docker no encontrado",
      dockerDialogDetail: "Se requiere Docker para ejecutar BIOwerk. Descarga Docker Desktop para continuar.",
      dockerDownload: "Descargar Docker",
      dialogCancel: "Cancelar",
      composeMissingTitle: "Error de configuración",
      composeMissingBody: "No se encontró docker-compose.yml en {path}",
      envCreatedTitle: "Configuración creada",
      envCreatedBody: "Se creó un archivo de configuración predeterminado",
      envCreatedDetail: "Revisa el archivo .env y reinicia la aplicación si necesitas cambiar algo.",
      startStarting: "Iniciando servicios de BIOwerk...",
      startSuccess: "Servicios iniciados correctamente",
      startFailure: "No se pudieron iniciar los servicios",
      stopStopping: "Deteniendo servicios de BIOwerk...",
      stopSuccess: "Servicios detenidos correctamente",
      stopFailure: "No se pudieron detener los servicios",
      localeUpdated: "Idioma actualizado a {language}"
    },
    docker: {
      installed: "✓ Instalado",
      notInstalled: "✗ No instalado",
      ready: "Docker está listo"
    },
    logs: {
      title: "Registros de servicio",
      ariaLabel: "Salida de registros del servicio"
    },
    settings: {
      configLabel: "Archivo de configuración",
      openEnv: "Abrir archivo .env",
      configHelper: "Edita variables de entorno, claves de API y configuración de servicios",
      composeLabel: "Archivo de Docker Compose",
      composeLocated: "Ubicado en:",
      localeLabel: "Idioma",
      localeHelper: "Cambia idiomas para validar truncamientos, diseño RTL y cobertura de traducción."
    }
  }
};

function resolveLocale(locale) {
  if (!locale) return "en";
  const normalized = locale.toLowerCase();
  if (AVAILABLE_LOCALES[normalized]) return normalized;
  const match = Object.keys(AVAILABLE_LOCALES).find((code) => normalized.startsWith(code));
  return match || "en";
}

function getLocaleMeta(locale) {
  return AVAILABLE_LOCALES[resolveLocale(locale)];
}

function getAvailableLocales() {
  return Object.entries(AVAILABLE_LOCALES).map(([code, meta]) => ({
    code,
    ...meta
  }));
}

function getIntlLocale(locale) {
  return getLocaleMeta(locale).intlLocale;
}

function translate(locale, key, variables = {}) {
  const targetLocale = resolveLocale(locale);
  const segments = key.split(".");
  const findValue = (tree) => segments.reduce((acc, part) => (acc && acc[part] !== undefined ? acc[part] : null), tree);
  const value = findValue(translations[targetLocale]) ?? findValue(translations.en) ?? key;
  const processed = targetLocale === "pseudo" ? pseudoize(String(value)) : String(value);
  return applyTemplate(processed, variables);
}

function applyTemplate(template, variables) {
  return template.replace(/\{(\w+)\}/g, (_, key) => {
    return variables[key] !== undefined ? variables[key] : `{${key}}`;
  });
}

function pseudoize(value) {
  const accentMap = {
    a: "å",
    A: "Å",
    e: "ë",
    E: "Ë",
    i: "ï",
    I: "Ï",
    o: "ø",
    O: "Ø",
    u: "ü",
    U: "Ü",
    y: "ÿ",
    Y: "Ÿ",
    c: "ç",
    C: "Ç",
    n: "ñ",
    N: "Ñ"
  };

  let inPlaceholder = false;
  const transformed = value
    .split("")
    .map((char) => {
      if (char === "{") inPlaceholder = true;
      if (char === "}") inPlaceholder = false;
      if (inPlaceholder) return char;
      return accentMap[char] || `${char}`;
    })
    .join("");

  return `⟪ ${transformed} ⟫`;
}

function isRTL(locale) {
  return getLocaleMeta(locale).direction === "rtl";
}

function formatDateTime(locale, date) {
  const intlLocale = getIntlLocale(locale);
  return new Intl.DateTimeFormat(intlLocale, {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  }).format(date);
}

function formatNumber(locale, value) {
  const intlLocale = getIntlLocale(locale);
  return new Intl.NumberFormat(intlLocale).format(value);
}

module.exports = {
  translations,
  resolveLocale,
  translate,
  formatDateTime,
  formatNumber,
  isRTL,
  getAvailableLocales,
  getLocaleMeta
};
