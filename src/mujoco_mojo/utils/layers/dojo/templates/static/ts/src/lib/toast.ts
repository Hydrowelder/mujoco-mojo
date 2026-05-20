export type ToastType = 'success' | 'error' | 'info';

export interface ToastMixin {
  showToast: boolean;
  toastMessage: string;
  toastType: ToastType;
  notify(msg: string, type?: ToastType): void;
}

export function createToastMixin(): ToastMixin {
  return {
    showToast: false,
    toastMessage: '',
    toastType: 'success',
    notify(msg: string, type: ToastType = 'success') {
      this.toastMessage = msg;
      this.toastType = type;
      this.showToast = true;
      setTimeout(() => { this.showToast = false; }, 3000);
      // also push to the global notification history (store may not be ready on first call)
      try {
        (Alpine.store('dojo') as { addNotification?: (m: string, t: string) => void }).addNotification?.(msg, type);
      } catch { /* ignore */ }
    },
  };
}
