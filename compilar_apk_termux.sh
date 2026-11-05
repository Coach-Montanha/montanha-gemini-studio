#!/data/data/com.termux/files/usr/bin/bash
# ==============================================================================
# Script de Compilação Rápida de APK Nativo no Termux (Montanha Gemini Studio)
# Gera o arquivo: /sdcard/Download/MontanhaGeminiStudio.apk
# ==============================================================================

set -e
echo "==> [1/5] Verificando dependências de build no Termux..."
pkg update -y >/dev/null 2>&1 || true
pkg install -y openjdk-17 aapt apksigner ecj dx >/dev/null 2>&1 || true

WORKDIR="$HOME/build_gemini_apk"
rm -rf "$WORKDIR"
mkdir -p "$WORKDIR/src/com/montanhagemini/app"
mkdir -p "$WORKDIR/res/values"
mkdir -p "$WORKDIR/obj"
mkdir -p "$WORKDIR/bin"

echo "==> [2/5] Gerando fontes e manifest..."
cat << 'EOF' > "$WORKDIR/AndroidManifest.xml"
<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    package="com.montanhagemini.app"
    android:versionCode="1"
    android:versionName="1.0">
    <uses-permission android:name="android.permission.INTERNET" />
    <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />
    <uses-permission android:name="android.permission.WRITE_EXTERNAL_STORAGE" />
    <uses-permission android:name="android.permission.READ_EXTERNAL_STORAGE" />
    <application
        android:label="Montanha Gemini Studio"
        android:usesCleartextTraffic="true"
        android:theme="@android:style/Theme.DeviceDefault.NoActionBar">
        <activity
            android:name=".MainActivity"
            android:exported="true"
            android:configChanges="orientation|screenSize|keyboardHidden">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
    </application>
</manifest>
EOF

cat << 'EOF' > "$WORKDIR/src/com/montanhagemini/app/MainActivity.java"
package com.montanhagemini.app;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.app.DownloadManager;
import android.content.Context;
import android.net.Uri;
import android.os.Bundle;
import android.os.Environment;
import android.view.WindowManager;
import android.webkit.DownloadListener;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;

public class MainActivity extends Activity {
    private WebView webView;

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        getWindow().setFlags(
            WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS,
            WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS
        );

        webView = new WebView(this);
        setContentView(webView);

        WebSettings ws = webView.getSettings();
        ws.setJavaScriptEnabled(true);
        ws.setDomStorageEnabled(true);
        ws.setAllowFileAccess(true);
        ws.setAllowContentAccess(true);
        ws.setMediaPlaybackRequiresUserGesture(false);

        webView.setWebViewClient(new WebViewClient());
        webView.setWebChromeClient(new WebChromeClient());

        webView.setDownloadListener(new DownloadListener() {
            @Override
            public void onDownloadStart(String url, String userAgent, String contentDisposition, String mimeType, long contentLength) {
                try {
                    DownloadManager.Request request = new DownloadManager.Request(Uri.parse(url));
                    request.setMimeType(mimeType);
                    request.setDescription("Baixando arquivo do Montanha Gemini Studio...");
                    request.setTitle(url.substring(url.lastIndexOf("/") + 1));
                    request.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
                    request.setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, url.substring(url.lastIndexOf("/") + 1));

                    DownloadManager dm = (DownloadManager) getSystemService(Context.DOWNLOAD_SERVICE);
                    if (dm != null) {
                        dm.enqueue(request);
                        Toast.makeText(MainActivity.this, "Baixando para a pasta Downloads...", Toast.LENGTH_SHORT).show();
                    }
                } catch (Exception e) {
                    Toast.makeText(MainActivity.this, "Erro no download: " + e.getMessage(), Toast.LENGTH_SHORT).show();
                }
            }
        });

        webView.loadUrl("https://montanha-gemini-studio.vercel.app");
    }

    @Override
    public void onBackPressed() {
        if (webView.canGoBack()) {
            webView.goBack();
        } else {
            super.onBackPressed();
        }
    }
}
EOF

ANDROID_JAR="/data/data/com.termux/files/usr/share/java/android.jar"
if [ ! -f "$ANDROID_JAR" ]; then
    echo "==> Baixando android.jar oficial..."
    curl -sL -o "$ANDROID_JAR" "https://raw.githubusercontent.com/rendiix/termux-nerdfont/master/android.jar" || \
    curl -sL -o "$ANDROID_JAR" "https://github.com/Sable/android-platforms/raw/master/android-28/android.jar"
fi

echo "==> [3/5] Compilando recursos com aapt..."
aapt package -f -m -J "$WORKDIR/src" -M "$WORKDIR/AndroidManifest.xml" -S "$WORKDIR/res" -I "$ANDROID_JAR"

echo "==> [4/5] Compilando Java com ecj..."
ecj -d "$WORKDIR/obj" -classpath "$ANDROID_JAR" $(find "$WORKDIR/src" -name "*.java")

echo "==> Gerando classes.dex..."
dx --dex --output="$WORKDIR/bin/classes.dex" "$WORKDIR/obj"

echo "==> [5/5] Montando e assinando APK..."
aapt package -f -M "$WORKDIR/AndroidManifest.xml" -S "$WORKDIR/res" -I "$ANDROID_JAR" -F "$WORKDIR/bin/unsigned.apk"
cd "$WORKDIR/bin"
aapt add unsigned.apk classes.dex >/dev/null

# Assinar APK com chave de debug
if [ ! -f "$HOME/.android/debug.keystore" ]; then
    mkdir -p "$HOME/.android"
    keytool -genkeypair -v -keystore "$HOME/.android/debug.keystore" -alias androiddebugkey -keypass android -storepass android -keyalg RSA -keysize 2048 -validity 10000 -dname "CN=AndroidDebug,O=Android,C=US" >/dev/null 2>&1
fi

apksigner sign --ks "$HOME/.android/debug.keystore" --ks-pass pass:android --out "/sdcard/Download/MontanhaGeminiStudio.apk" unsigned.apk

echo "=========================================================="
echo "✓ APK COMPILADO COM SUCESSO!"
echo "👉 Local: /sdcard/Download/MontanhaGeminiStudio.apk"
echo "Abra o aplicativo 'Arquivos > Downloads' no seu celular e instale!"
echo "=========================================================="
