// Where the two services are. This file is for local runs (compose); the deploy
// workflow overwrites it with the Azure URLs, so no URL is hardcoded in app.js.
window.MAISON_CONFIG = {
  specs: "http://localhost:8000",
  samples: "http://localhost:8001",
};
