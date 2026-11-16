package com.valjdakosta.nastava;

import android.content.Intent;
import android.provider.Settings;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

/** The app's notification settings, for the site's "Otvori podešavanja" (site.js) when they are off: Capacitor's
 *  plugins can't open them. */
@CapacitorPlugin(name = "NotifySettings")
public class NotifySettings extends Plugin {

    @PluginMethod
    public void open(PluginCall call) {
        getActivity().startActivity(new Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS)
            .putExtra(Settings.EXTRA_APP_PACKAGE, getContext().getPackageName()));
        call.resolve();
    }
}
