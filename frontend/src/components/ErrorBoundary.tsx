import { Component, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center h-screen gap-4 bg-(--color-background)">
          <div className="w-16 h-16 rounded-full bg-(--color-secondary) flex items-center justify-center">
            <span className="text-[24px] text-(--color-danger) font-semibold">!</span>
          </div>
          <p className="text-[17px] font-semibold text-(--color-foreground)">Something went wrong</p>
          <p className="text-[13px] text-(--color-ink-2) max-w-md text-center">
            {this.state.error?.message || "An unexpected error occurred"}
          </p>
          <button
            onClick={() => window.location.reload()}
            className="px-4 h-9 rounded-md bg-(--color-primary) text-(--color-primary-foreground) text-[13px] font-medium hover:opacity-90 transition-colors"
          >
            Reload Page
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
