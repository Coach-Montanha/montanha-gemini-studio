package com.montanhagemini.app;

import android.Manifest;
import android.annotation.SuppressLint;
import android.app.Activity;
import android.app.DownloadManager;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.os.Handler;
import android.os.Looper;
import android.speech.RecognitionListener;
import android.speech.RecognizerIntent;
import android.speech.SpeechRecognizer;
import android.speech.tts.TextToSpeech;
import android.speech.tts.UtteranceProgressListener;
import android.view.WindowManager;
import android.webkit.DownloadListener;
import android.webkit.JavascriptInterface;
import android.webkit.PermissionRequest;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;
import java.io.BufferedReader;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Iterator;
import java.util.Locale;
import java.util.Map;
import org.json.JSONObject;

public class MainActivity extends Activity implements TextToSpeech.OnInitListener {
    private WebView webView;
    private SpeechRecognizer speechRecognizer;
    private TextToSpeech tts;
    private boolean ttsReady = false;
    private final Handler mainHandler = new Handler(Looper.getMainLooper());
    private static final int PERMISSION_REQ_CODE = 200;

    // Configuracoes do Cofre Persistente (sobrevive a exclusao do app)
    private static final String VAULT_PREFS = "montanha_persistent_vault";
    private static final String VAULT_DIR_NAME = "MontanhaStudio";
    private static final String VAULT_FILE_NAME = "vault_profile.json";

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        // Barra de status translucida e areas seguras
        getWindow().clearFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN);

        checkAndRequestAudioPermissions();

        try {
            tts = new TextToSpeech(this, this);
        } catch (Exception ignored) {}

        webView = new WebView(this);
        setContentView(webView);

        WebSettings ws = webView.getSettings();
        ws.setJavaScriptEnabled(true);
        ws.setDomStorageEnabled(true);
        ws.setAllowFileAccess(true);
        ws.setAllowContentAccess(true);
        ws.setMediaPlaybackRequiresUserGesture(false);

        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onPermissionRequest(final PermissionRequest request) {
                runOnUiThread(new Runnable() {
                    @Override
                    public void run() {
                        try {
                            request.grant(request.getResources());
                        } catch (Exception ignored) {}
                    }
                });
            }
        });

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public void onPageFinished(WebView view, String url) {
                super.onPageFinished(view, url);
                // Restaura automaticamente credenciais e dados se o localStorage estiver limpo
                view.evaluateJavascript("if (window.syncRestoredVault) { window.syncRestoredVault(); }", null);
            }
        });

        // Pontes nativas: Voz continua e Cofre de Armazenamento Persistente
        webView.addJavascriptInterface(new AndroidVoiceBridge(), "AndroidVoiceBridge");
        webView.addJavascriptInterface(new AndroidStorageBridge(), "AndroidStorageBridge");

        webView.setDownloadListener(new DownloadListener() {
            @Override
            public void onDownloadStart(String url, String userAgent, String contentDisposition, String mimeType, long contentLength) {
                try {
                    DownloadManager.Request request = new DownloadManager.Request(Uri.parse(url));
                    request.setMimeType(mimeType);
                    request.setDescription("Baixando arquivo do Montanha AI Studio...");
                    request.setTitle(url.substring(url.lastIndexOf("/") + 1));
                    request.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
                    request.setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, url.substring(url.lastIndexOf("/") + 1));

                    DownloadManager dm = (DownloadManager) getSystemService(Context.DOWNLOAD_SERVICE);
                    if (dm != null) {
                        dm.enqueue(request);
                        Toast.makeText(MainActivity.this, "Baixando para pasta Downloads...", Toast.LENGTH_SHORT).show();
                    }
                } catch (Exception e) {
                    Toast.makeText(MainActivity.this, "Erro no download: " + e.getMessage(), Toast.LENGTH_SHORT).show();
                }
            }
        });

        webView.loadUrl("https://montanha-gemini-studio.vercel.app");
    }

    private void checkAndRequestAudioPermissions() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            ArrayList<String> perms = new ArrayList<String>();
            if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
                perms.add(Manifest.permission.RECORD_AUDIO);
            }
            if (checkSelfPermission(Manifest.permission.WRITE_EXTERNAL_STORAGE) != PackageManager.PERMISSION_GRANTED && Build.VERSION.SDK_INT <= 29) {
                perms.add(Manifest.permission.WRITE_EXTERNAL_STORAGE);
            }
            if (!perms.isEmpty()) {
                requestPermissions(perms.toArray(new String[0]), PERMISSION_REQ_CODE);
            }
        }
    }

    private File getVaultFile(boolean useDownloads) {
        try {
            File base = Environment.getExternalStoragePublicDirectory(
                useDownloads ? Environment.DIRECTORY_DOWNLOADS : Environment.DIRECTORY_DOCUMENTS
            );
            File dir = new File(base, VAULT_DIR_NAME);
            if (!dir.exists()) {
                dir.mkdirs();
            }
            return new File(dir, VAULT_FILE_NAME);
        } catch (Exception e) {
            return null;
        }
    }

    private synchronized void persistVaultToFile(String jsonStr) {
        for (boolean useDownloads : new boolean[]{false, true}) {
            try {
                File target = getVaultFile(useDownloads);
                if (target != null) {
                    try (OutputStreamWriter osw = new OutputStreamWriter(new FileOutputStream(target), StandardCharsets.UTF_8)) {
                        osw.write(jsonStr);
                        osw.flush();
                    }
                }
            } catch (Exception ignored) {}
        }
    }

    private synchronized String readVaultFromFile() {
        for (boolean useDownloads : new boolean[]{false, true}) {
            try {
                File target = getVaultFile(useDownloads);
                if (target != null && target.exists() && target.length() > 2) {
                    StringBuilder sb = new StringBuilder();
                    try (BufferedReader br = new BufferedReader(new InputStreamReader(new FileInputStream(target), StandardCharsets.UTF_8))) {
                        String line;
                        while ((line = br.readLine()) != null) {
                            sb.append(line).append("\n");
                        }
                    }
                    String res = sb.toString().trim();
                    if (!res.isEmpty() && res.startsWith("{")) {
                        return res;
                    }
                }
            } catch (Exception ignored) {}
        }
        return null;
    }

    @Override
    public void onInit(int status) {
        if (status == TextToSpeech.SUCCESS) {
            try {
                int res = tts.setLanguage(new Locale("pt", "BR"));
                if (res != TextToSpeech.LANG_MISSING_DATA && res != TextToSpeech.LANG_NOT_SUPPORTED) {
                    ttsReady = true;
                    tts.setOnUtteranceProgressListener(new UtteranceProgressListener() {
                        @Override public void onStart(String utteranceId) {}
                        @Override
                        public void onDone(String utteranceId) {
                            mainHandler.post(new Runnable() {
                                @Override
                                public void run() {
                                    if (webView != null) {
                                        webView.evaluateJavascript("window.onNativeSpeechUtteranceDone && window.onNativeSpeechUtteranceDone();", null);
                                    }
                                }
                            });
                        }
                        @Override public void onError(String utteranceId) {}
                    });
                }
            } catch (Exception ignored) {}
        }
    }

    // =========================================================================
    // PONTE 1: ARMAZENAMENTO PERSISTENTE & AUTO-BACKUP NO DISPOSITIVO
    // =========================================================================
    public class AndroidStorageBridge {
        private final SharedPreferences prefs;

        public AndroidStorageBridge() {
            prefs = getSharedPreferences(VAULT_PREFS, Context.MODE_PRIVATE);
            syncFromPersistentVaultFile();
        }

        private synchronized void syncFromPersistentVaultFile() {
            try {
                Map<String, ?> all = prefs.getAll();
                if (all == null || all.isEmpty()) {
                    String fileData = readVaultFromFile();
                    if (fileData != null && !fileData.trim().isEmpty()) {
                        JSONObject json = new JSONObject(fileData);
                        SharedPreferences.Editor editor = prefs.edit();
                        Iterator<String> keys = json.keys();
                        while (keys.hasNext()) {
                            String k = keys.next();
                            editor.putString(k, json.optString(k, ""));
                        }
                        editor.apply();
                    }
                }
            } catch (Exception ignored) {}
        }

        @JavascriptInterface
        public void saveItem(String key, String value) {
            try {
                SharedPreferences.Editor editor = prefs.edit();
                editor.putString(key, value);
                editor.apply();

                new Thread(new Runnable() {
                    @Override
                    public void run() {
                        try {
                            Map<String, ?> all = prefs.getAll();
                            JSONObject json = new JSONObject();
                            for (Map.Entry<String, ?> entry : all.entrySet()) {
                                json.put(entry.getKey(), entry.getValue());
                            }
                            persistVaultToFile(json.toString());
                        } catch (Exception ignored) {}
                    }
                }).start();
            } catch (Exception ignored) {}
        }

        @JavascriptInterface
        public String getItem(String key) {
            String val = prefs.getString(key, "");
            if (val == null || val.isEmpty()) {
                syncFromPersistentVaultFile();
                val = prefs.getString(key, "");
            }
            return val != null ? val : "";
        }

        @JavascriptInterface
        public String getAllData() {
            try {
                syncFromPersistentVaultFile();
                Map<String, ?> all = prefs.getAll();
                JSONObject json = new JSONObject();
                for (Map.Entry<String, ?> entry : all.entrySet()) {
                    json.put(entry.getKey(), entry.getValue());
                }
                return json.toString();
            } catch (Exception e) {
                return "{}";
            }
        }

        @JavascriptInterface
        public void backupAll(String jsonString) {
            try {
                JSONObject json = new JSONObject(jsonString);
                SharedPreferences.Editor editor = prefs.edit();
                Iterator<String> keys = json.keys();
                while (keys.hasNext()) {
                    String k = keys.next();
                    editor.putString(k, json.optString(k, ""));
                }
                editor.apply();
                persistVaultToFile(jsonString);
            } catch (Exception ignored) {}
        }

        @JavascriptInterface
        public boolean isStorageAvailable() {
            return true;
        }
    }

    // =========================================================================
    // PONTE 2: VOZ E RECONHECIMENTO CONTINUO
    // =========================================================================
    public class AndroidVoiceBridge {
        @JavascriptInterface
        public boolean isNativeAvailable() {
            return SpeechRecognizer.isRecognitionAvailable(MainActivity.this);
        }

        @JavascriptInterface
        public void startSpeechRecognition() {
            mainHandler.post(new Runnable() {
                @Override
                public void run() {
                    try {
                        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                            if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
                                checkAndRequestAudioPermissions();
                                return;
                            }
                        }
                        if (speechRecognizer != null) {
                            try { speechRecognizer.destroy(); } catch (Exception ignored) {}
                        }
                        speechRecognizer = SpeechRecognizer.createSpeechRecognizer(MainActivity.this);
                        speechRecognizer.setRecognitionListener(new RecognitionListener() {
                            @Override public void onReadyForSpeech(Bundle params) {}
                            @Override public void onBeginningOfSpeech() {}
                            @Override public void onRmsChanged(float rmsdB) {}
                            @Override public void onBufferReceived(byte[] buffer) {}
                            @Override public void onEndOfSpeech() {
                                webView.evaluateJavascript("window.onNativeSpeechEnd && window.onNativeSpeechEnd();", null);
                            }
                            @Override
                            public void onError(int error) {
                                webView.evaluateJavascript("window.onNativeSpeechError && window.onNativeSpeechError(" + error + ");", null);
                            }
                            @Override
                            public void onResults(Bundle results) {
                                ArrayList<String> matches = results.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);
                                if (matches != null && !matches.isEmpty()) {
                                    String text = matches.get(0).replace("'", "\\'").replace("\n", " ");
                                    webView.evaluateJavascript("window.onNativeSpeechResult && window.onNativeSpeechResult('" + text + "');", null);
                                }
                            }
                            @Override public void onPartialResults(Bundle partialResults) {}
                            @Override public void onEvent(int eventType, Bundle params) {}
                        });

                        Intent intent = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH);
                        intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM);
                        intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE, "pt-BR");
                        intent.putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1);
                        speechRecognizer.startListening(intent);
                    } catch (Exception e) {
                        webView.evaluateJavascript("window.onNativeSpeechError && window.onNativeSpeechError(-1);", null);
                    }
                }
            });
        }

        @JavascriptInterface
        public void stopSpeechRecognition() {
            mainHandler.post(new Runnable() {
                @Override
                public void run() {
                    if (speechRecognizer != null) {
                        try { speechRecognizer.stopListening(); } catch (Exception ignored) {}
                    }
                }
            });
        }

        @JavascriptInterface
        public void speak(final String text) {
            mainHandler.post(new Runnable() {
                @Override
                public void run() {
                    if (ttsReady && tts != null) {
                        try {
                            Bundle params = new Bundle();
                            params.putString(TextToSpeech.Engine.KEY_PARAM_UTTERANCE_ID, "LIVE_CALL");
                            tts.speak(text, TextToSpeech.QUEUE_FLUSH, params, "LIVE_CALL");
                        } catch (Exception ignored) {}
                    }
                }
            });
        }

        @JavascriptInterface
        public void stopSpeaking() {
            mainHandler.post(new Runnable() {
                @Override
                public void run() {
                    if (tts != null) {
                        try { tts.stop(); } catch (Exception ignored) {}
                    }
                }
            });
        }
    }

    @Override
    protected void onDestroy() {
        if (speechRecognizer != null) {
            try { speechRecognizer.destroy(); } catch (Exception ignored) {}
        }
        if (tts != null) {
            try {
                tts.stop();
                tts.shutdown();
            } catch (Exception ignored) {}
        }
        super.onDestroy();
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
