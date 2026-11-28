import { createContext, useContext, type ReactNode } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, TextInput, View, type TextInputProps } from 'react-native';

export const palettes = {
  light: { background: '#f5f6fc', panel: '#ffffff', text: '#172139', muted: '#536079', border: '#c4cddd', accent: '#4b35b5', onAccent: '#ffffff', danger: '#b32532', soft: '#ece8fc' },
  dark: { background: '#0c1323', panel: '#151f33', text: '#edf0fa', muted: '#b4bfd3', border: '#47546b', accent: '#b9a9ff', onAccent: '#17112e', danger: '#ffb0b5', soft: '#29223f' },
};
export type Palette = typeof palettes.light;
export const Theme = createContext<Palette>(palettes.light);
export const useTheme = () => useContext(Theme);
export const layout = StyleSheet.create({
  page: { flex: 1 }, content: { padding: 20, gap: 16, width: '100%', maxWidth: 960, alignSelf: 'center' },
  row: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: 10 },
  title: { fontSize: 25, fontWeight: '700', lineHeight: 32 }, subtitle: { fontSize: 18, fontWeight: '600', lineHeight: 25 },
  text: { fontSize: 16, lineHeight: 24 }, small: { fontSize: 13, lineHeight: 20 },
});
export function Copy({ children, muted = false, small = false }: { children: ReactNode; muted?: boolean; small?: boolean }) {
  const color = useTheme(); return <Text selectable style={[small ? layout.small : layout.text, { color: muted ? color.muted : color.text }]}>{children}</Text>;
}
export function Heading({ children, level = 1 }: { children: ReactNode; level?: 1 | 2 }) {
  const color = useTheme(); return <Text accessibilityRole="header" style={[level === 1 ? layout.title : layout.subtitle, { color: color.text }]}>{children}</Text>;
}
export function Panel({ children }: { children: ReactNode }) {
  const color = useTheme(); return <View style={{ padding: 18, borderRadius: 18, borderWidth: 1, borderColor: color.border, backgroundColor: color.panel, gap: 12 }}>{children}</View>;
}
export function Button({ children, onPress, disabled = false, secondary = false, selected = false, danger = false, testID }: { children: string; onPress: () => void; disabled?: boolean; secondary?: boolean; selected?: boolean; danger?: boolean; testID?: string }) {
  const color = useTheme();
  return <Pressable accessibilityRole="button" accessibilityState={{ disabled, ...(selected ? { selected: true } : {}) }} disabled={disabled} onPress={onPress} testID={testID}
    style={({ pressed }) => ({ minHeight: 48, paddingHorizontal: 16, paddingVertical: 12, borderRadius: 12, borderWidth: 1, borderColor: danger ? color.danger : color.accent, backgroundColor: secondary ? selected ? color.soft : 'transparent' : color.accent, opacity: disabled ? 0.48 : pressed ? 0.75 : 1, justifyContent: 'center' })}>
    <Text style={{ fontSize: 16, fontWeight: '600', textAlign: 'center', color: danger ? color.danger : secondary ? color.accent : color.onAccent }}>{children}</Text>
  </Pressable>;
}
export function Field({ label, ...props }: TextInputProps & { label: string }) {
  const color = useTheme(); return <View style={{ gap: 6 }}><Copy>{label}</Copy><TextInput {...props} accessibilityLabel={label} placeholderTextColor={color.muted} style={{ minHeight: props.multiline ? 110 : 48, borderWidth: 1, borderColor: color.border, borderRadius: 12, padding: 12, fontSize: 16, lineHeight: 23, color: color.text, backgroundColor: color.background, textAlignVertical: props.multiline ? 'top' : 'center' }} /></View>;
}
export function Notice({ message, error = false }: { message: string; error?: boolean }) {
  const color = useTheme(); return message ? <Text accessibilityRole={error ? 'alert' : 'text'} accessibilityLiveRegion="polite" style={[layout.text, { color: error ? color.danger : color.muted }]}>{message}</Text> : null;
}
export function Busy({ label = 'Loading…' }: { label?: string }) { const color = useTheme(); return <View style={layout.row}><ActivityIndicator color={color.accent} /><Copy muted>{label}</Copy></View>; }
export const failure = (reason: unknown) => reason instanceof Error && !reason.name.startsWith('Zod') ? reason.message : 'The service returned an unsupported response. Please try again later.';
