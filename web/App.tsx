import { StatusBar } from "expo-status-bar";
import React from "react";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { Navigation } from "./src/navigation";
import { SessionProvider } from "./src/store/session";

export default function App() {
  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <SafeAreaProvider>
        <SessionProvider>
          <StatusBar style="light" />
          <Navigation />
        </SessionProvider>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}
