package com.montanhagemini.app;

import android.Manifest;
import android.annotation.SuppressLint;
import android.app.Activity;
import android.app.DownloadManager;
import android.content.Context;
import android.content.Intent;
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
import java.util.ArrayList;
import java.util.Locale;

public class MainActivity extends Activity implements TextToSpeech.OnInitListener {
    private WebView webView;
    private SpeechRecognizer speechRecognizer;
    private TextToSpeech tts;
    private boolean ttsReady = false;
    private final Handler mainHandler = new Handler(Looper.getMainLooper());
    private static final int PERMISSION_REQ_CODE = 200;

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        // Barra de status translúcida e áreas seguras
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
                runOnUiThread(() -> {
                    try {
                        request.grant(request.getResources());
                    } catch (Exception ignored) {}
                });
            }
        });

        webView.setWebViewClient(new WebViewClient());

        // Ponte nativa para conversas de áudio e reconhecimento de voz contínuo
        webView.addJavascriptInterface(new AndroidVoiceBridge(), "AndroidVoiceBridge");

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
            if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
                requestPermissions(new String[]{
                    Manifest.permission.RECORD_AUDIO,
                    Manifest.permission.MODIFY_AUDIO_SETTINGS
                }, PERMISSION_REQ_CODE);
            }
        }
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
                            mainHandler.post(() -> {
                                if (webView != null) {
                                    webView.evaluateJavascript("window.onNativeSpeechUtteranceDone && window.onNativeSpeechUtteranceDone();", null);
                                }
                            });
                        }
                        @Override public void onError(String utteranceId) {}
                    });
                }
            } catch (Exception ignored) {}
        }
    }

    public class AndroidVoiceBridge {
        @JavascriptInterface
        public boolean isNativeAvailable() {
            return SpeechRecognizer.isRecognitionAvailable(MainActivity.this);
        }

        @JavascriptInterface
        public void startSpeechRecognition() {
            mainHandler.post(() -> {
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
            });
        }

        @JavascriptInterface
        public void stopSpeechRecognition() {
            mainHandler.post(() -> {
                if (speechRecognizer != null) {
                    try { speechRecognizer.stopListening(); } catch (Exception ignored) {}
                }
            });
        }

        @JavascriptInterface
        public void speak(String text) {
            mainHandler.post(() -> {
                if (ttsReady && tts != null) {
                    try {
                        Bundle params = new Bundle();
                        params.putString(TextToSpeech.Engine.KEY_PARAM_UTTERANCE_ID, "LIVE_CALL");
                        tts.speak(text, TextToSpeech.QUEUE_FLUSH, params, "LIVE_CALL");
                    } catch (Exception ignored) {}
                }
            });
        }

        @JavascriptInterface
        public void stopSpeaking() {
            mainHandler.post(() -> {
                if (tts != null) {
                    try { tts.stop(); } catch (Exception ignored) {}
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
