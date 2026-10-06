export interface SuggestionMessage {
  role: "user" | "assistant";
  content: string;
}

export interface SuggestionsConfigResponse {
  enabled: boolean;
  max_suggestions: number;
}

export interface SuggestionsPayload {
  messages: SuggestionMessage[];
  n?: number;
  model_id?: string;
}

export interface SuggestionsResponse {
  suggestions: string[];
}
