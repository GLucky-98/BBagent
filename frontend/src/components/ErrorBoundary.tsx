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
        <div className="flex flex-col items-center justify-center h-screen gap-4 bg-[--color-background]">
          <div className="w-16 h-16 rounded-full bg-red-100 flex items-center justify-center">
            <span className="text-2xl text-red-500">!</span>
          </div>
          <p className="text-lg font-medium text-[--color-foreground]">Something went wrong</p>
          <p className="text-sm text-[--color-muted-foreground] max-w-md text-center">
            {this.state.error?.message || "An unexpected error occurred"}
          </p>
          <button
            onClick={() => window.location.reload()}
            className="px-4 py-2 rounded-lg bg-[--color-primary] text-[--color-primary-foreground] text-sm hover:opacity-90"
          >
            Reload Page
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
