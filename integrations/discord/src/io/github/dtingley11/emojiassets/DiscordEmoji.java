package io.github.dtingley11.emojiassets;

import android.content.res.AssetManager;
import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.HashSet;
import java.util.Set;
import java.util.concurrent.atomic.AtomicInteger;
import de.robv.android.xposed.IXposedHookLoadPackage;
import de.robv.android.xposed.IXposedHookZygoteInit;
import de.robv.android.xposed.XC_MethodHook;
import de.robv.android.xposed.XposedBridge;
import de.robv.android.xposed.XposedHelpers;
import de.robv.android.xposed.callbacks.XC_LoadPackage;

public final class DiscordEmoji implements IXposedHookLoadPackage, IXposedHookZygoteInit {
    private static String modulePath;
    private static boolean installed;
    private static final AtomicInteger logged = new AtomicInteger();

    @Override
    public void initZygote(StartupParam param) {
        modulePath = param.modulePath;
    }

    @Override
    public void handleLoadPackage(XC_LoadPackage.LoadPackageParam param) {
        if (installed || modulePath == null) return;

        installed = true;
        try {
            final AssetManager replacements = (AssetManager) XposedHelpers.newInstance(AssetManager.class);
            int cookie = (Integer) XposedHelpers.callMethod(replacements, "addAssetPath", modulePath);
            if (cookie == 0) throw new IllegalStateException("Cannot open add-on assets");
            final Set<String> names = new HashSet<>();
            try (BufferedReader reader = new BufferedReader(new InputStreamReader(
                    replacements.open("replacement-list.txt"), StandardCharsets.UTF_8))) {
                String line;
                while ((line = reader.readLine()) != null) names.add(line);
            }

            // AssetManager is hooked only in Discord's scoped processes. Missing
            // images fall through to Discord, preserving custom/unsupported emoji.
            XposedBridge.hookAllMethods(AssetManager.class, "open", new XC_MethodHook() {
                @Override
                protected void beforeHookedMethod(MethodHookParam hook) {
                    if (hook.thisObject == replacements || hook.args.length == 0
                            || !(hook.args[0] instanceof String)) return;
                    String name = assetName((String) hook.args[0], names);
                    if (name == null) return;
                    try {
                        int mode = hook.args.length > 1 ? (Integer) hook.args[1] : AssetManager.ACCESS_STREAMING;
                        hook.setResult(replacements.open("discord/" + name, mode));
                        logReplacement(name);
                    } catch (Exception error) {
                        logError(error);
                    }
                }
            });
            XposedBridge.hookAllMethods(AssetManager.class, "openFd", new XC_MethodHook() {
                @Override
                protected void beforeHookedMethod(MethodHookParam hook) {
                    if (hook.thisObject == replacements || hook.args.length == 0
                            || !(hook.args[0] instanceof String)) return;
                    String name = assetName((String) hook.args[0], names);
                    if (name == null) return;
                    try {
                        hook.setResult(replacements.openFd("discord/" + name));
                        logReplacement(name);
                    } catch (Exception error) {
                        logError(error);
                    }
                }
            });
            XposedBridge.log("iOS Emoji Assets: ready in " + param.processName + "; " + names.size() + " images");
        } catch (Throwable error) {
            XposedBridge.log("iOS Emoji Assets: initialization failed; leaving Discord unchanged: " + error);
        }
    }

    private static String assetName(String path, Set<String> names) {
        String name = path.startsWith("assets/") ? path.substring(7) : path;
        return name.indexOf('/') < 0 && names.contains(name) ? name : null;
    }

    private static void logReplacement(String name) {
        if (logged.getAndIncrement() < 8) XposedBridge.log("iOS Emoji Assets: replaced " + name);
    }

    private static void logError(Exception error) {
        if (logged.getAndIncrement() < 8) XposedBridge.log("iOS Emoji Assets: fallback to original: " + error);
    }
}
