const { app, BrowserWindow, ipcMain, Tray, Menu, shell, dialog } = require('electron');
const path = require('path');
const { exec, spawn } = require('child_process');
const axios = require('axios');
const fs = require('fs');

let mainWindow = null;
let tray = null;
let dockerProcess = null;

// Application paths
const isDev = !app.isPackaged;
const appPath = isDev ? path.join(__dirname, '..', '..') : path.join(process.resourcesPath, 'app');
const composePath = path.join(appPath, 'docker-compose.yml');

// Service health status
let servicesStatus = {
  mesh: { name: 'Mesh Gateway', url: 'http://localhost:8080/health', status: 'stopped' },
  osteon: { name: 'Osteon (Writer)', url: 'http://localhost:8001/health', status: 'stopped' },
  myocyte: { name: 'Myocyte (Spreadsheet)', url: 'http://localhost:8002/health', status: 'stopped' },
  synapse: { name: 'Synapse (Presentation)', url: 'http://localhost:8003/health', status: 'stopped' },
  circadian: { name: 'Circadian (Scheduler)', url: 'http://localhost:8004/health', status: 'stopped' },
  nucleus: { name: 'Nucleus (Director)', url: 'http://localhost:8005/health', status: 'stopped' },
  grafana: { name: 'Grafana (Monitoring)', url: 'http://localhost:3000/api/health', status: 'stopped' },
  prometheus: { name: 'Prometheus', url: 'http://localhost:9090/-/healthy', status: 'stopped' }
};

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    icon: path.join(__dirname, 'assets', 'icon.png'),
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false
    },
    backgroundColor: '#1e1e1e',
    show: false,
    title: 'BIOwerk Control Panel'
  });

  mainWindow.loadFile('index.html');

  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
    checkDockerInstalled();
    checkServicesStatus();
  });

  mainWindow.on('close', (event) => {
    if (!app.isQuitting) {
      event.preventDefault();
      mainWindow.hide();
    }
  });

  // Development only
  if (isDev) {
    mainWindow.webContents.openDevTools();
  }
}

function createTray() {
  const iconPath = path.join(__dirname, 'assets', 'tray-icon.png');
  tray = new Tray(iconPath);

  const contextMenu = Menu.buildFromTemplate([
    {
      label: 'Show Control Panel',
      click: () => {
        mainWindow.show();
      }
    },
    { type: 'separator' },
    {
      label: 'Start Services',
      click: () => {
        startServices();
      }
    },
    {
      label: 'Stop Services',
      click: () => {
        stopServices();
      }
    },
    { type: 'separator' },
    {
      label: 'Open API Docs',
      click: () => {
        shell.openExternal('http://localhost:8080/docs');
      }
    },
    {
      label: 'Open Grafana',
      click: () => {
        shell.openExternal('http://localhost:3000');
      }
    },
    { type: 'separator' },
    {
      label: 'Quit',
      click: () => {
        app.isQuitting = true;
        stopServices().then(() => {
          app.quit();
        });
      }
    }
  ]);

  tray.setToolTip('BIOwerk Suite');
  tray.setContextMenu(contextMenu);

  tray.on('click', () => {
    mainWindow.show();
  });
}

// Check if Docker is installed
function checkDockerInstalled() {
  exec('docker --version', (error, stdout) => {
    if (error) {
      mainWindow.webContents.send('docker-status', {
        installed: false,
        message: 'Docker is not installed'
      });

      dialog.showMessageBox(mainWindow, {
        type: 'error',
        title: 'Docker Not Found',
        message: 'Docker is required to run BIOwerk',
        detail: 'Please install Docker Desktop from https://docker.com',
        buttons: ['Download Docker', 'Cancel']
      }).then((result) => {
        if (result.response === 0) {
          shell.openExternal('https://www.docker.com/products/docker-desktop');
        }
      });
    } else {
      mainWindow.webContents.send('docker-status', {
        installed: true,
        version: stdout.trim()
      });
      checkDockerRunning();
    }
  });
}

// Check if Docker daemon is running
function checkDockerRunning() {
  exec('docker info', (error) => {
    if (error) {
      mainWindow.webContents.send('docker-daemon-status', {
        running: false,
        message: 'Docker daemon is not running'
      });
    } else {
      mainWindow.webContents.send('docker-daemon-status', {
        running: true,
        message: 'Docker is ready'
      });
    }
  });
}

// Check services health status
async function checkServicesStatus() {
  for (const [key, service] of Object.entries(servicesStatus)) {
    try {
      await axios.get(service.url, { timeout: 2000 });
      servicesStatus[key].status = 'running';
    } catch (error) {
      servicesStatus[key].status = 'stopped';
    }
  }

  if (mainWindow) {
    mainWindow.webContents.send('services-status', servicesStatus);
  }
}

// Start Docker Compose services
function startServices() {
  if (!fs.existsSync(composePath)) {
    dialog.showErrorBox('Configuration Error',
      `docker-compose.yml not found at ${composePath}`);
    return Promise.reject(new Error('docker-compose.yml not found'));
  }

  // Check for .env file
  const envPath = path.join(appPath, '.env');
  if (!fs.existsSync(envPath)) {
    const envExamplePath = path.join(appPath, '.env.example');
    if (fs.existsSync(envExamplePath)) {
      fs.copyFileSync(envExamplePath, envPath);
      dialog.showMessageBox(mainWindow, {
        type: 'info',
        title: 'Configuration Created',
        message: 'A default configuration file has been created',
        detail: 'Please review the .env file and restart the application if you need to change any settings.'
      });
    }
  }

  return new Promise((resolve, reject) => {
    mainWindow.webContents.send('operation-status', {
      status: 'starting',
      message: 'Starting BIOwerk services...'
    });

    const compose = spawn('docker', ['compose', 'up', '-d'], {
      cwd: appPath,
      shell: true
    });

    let output = '';

    compose.stdout.on('data', (data) => {
      output += data.toString();
      mainWindow.webContents.send('operation-log', data.toString());
    });

    compose.stderr.on('data', (data) => {
      output += data.toString();
      mainWindow.webContents.send('operation-log', data.toString());
    });

    compose.on('close', (code) => {
      if (code === 0) {
        mainWindow.webContents.send('operation-status', {
          status: 'started',
          message: 'Services started successfully'
        });

        // Wait a bit for services to initialize
        setTimeout(() => {
          checkServicesStatus();
        }, 5000);

        resolve();
      } else {
        mainWindow.webContents.send('operation-status', {
          status: 'error',
          message: 'Failed to start services',
          details: output
        });
        reject(new Error('Failed to start services'));
      }
    });
  });
}

// Stop Docker Compose services
function stopServices() {
  return new Promise((resolve, reject) => {
    mainWindow.webContents.send('operation-status', {
      status: 'stopping',
      message: 'Stopping BIOwerk services...'
    });

    const compose = spawn('docker', ['compose', 'down'], {
      cwd: appPath,
      shell: true
    });

    compose.on('close', (code) => {
      if (code === 0) {
        mainWindow.webContents.send('operation-status', {
          status: 'stopped',
          message: 'Services stopped successfully'
        });
        checkServicesStatus();
        resolve();
      } else {
        mainWindow.webContents.send('operation-status', {
          status: 'error',
          message: 'Failed to stop services'
        });
        reject(new Error('Failed to stop services'));
      }
    });
  });
}

// Restart services
function restartServices() {
  stopServices().then(() => {
    setTimeout(() => {
      startServices();
    }, 2000);
  });
}

// View logs
function viewLogs(service = null) {
  const args = service ?
    ['compose', 'logs', '-f', '--tail=100', service] :
    ['compose', 'logs', '-f', '--tail=100'];

  const logs = spawn('docker', args, {
    cwd: appPath,
    shell: true
  });

  logs.stdout.on('data', (data) => {
    mainWindow.webContents.send('service-logs', {
      service: service || 'all',
      log: data.toString()
    });
  });

  logs.stderr.on('data', (data) => {
    mainWindow.webContents.send('service-logs', {
      service: service || 'all',
      log: data.toString()
    });
  });

  return logs;
}

// IPC Handlers
ipcMain.on('start-services', () => {
  startServices();
});

ipcMain.on('stop-services', () => {
  stopServices();
});

ipcMain.on('restart-services', () => {
  restartServices();
});

ipcMain.on('check-status', () => {
  checkDockerInstalled();
  checkServicesStatus();
});

ipcMain.on('view-logs', (event, service) => {
  viewLogs(service);
});

ipcMain.on('open-url', (event, url) => {
  shell.openExternal(url);
});

ipcMain.on('open-config', () => {
  const envPath = path.join(appPath, '.env');
  shell.openPath(envPath);
});

// App lifecycle
app.whenReady().then(() => {
  createWindow();
  createTray();

  // Check status periodically
  setInterval(() => {
    checkServicesStatus();
  }, 10000);
});

app.on('window-all-closed', () => {
  // On macOS, keep the app running in the tray
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  } else {
    mainWindow.show();
  }
});

app.on('before-quit', () => {
  app.isQuitting = true;
});
