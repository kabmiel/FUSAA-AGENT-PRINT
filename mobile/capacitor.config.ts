import type { CapacitorConfig } from "@capacitor/cli";

const config: CapacitorConfig = {
  appId: "com.fusaa.service",
  appName: "FUSAA Service",
  webDir: "www",
  server: {
    // L'APK charge l'interface officielle : une seule version à maintenir.
    url: "https://fusaa-agent-print.onrender.com",
    cleartext: false,
    allowNavigation: ["fusaa-agent-print.onrender.com"]
  },
  android: { backgroundColor: "#07111f" }
};

export default config;
