import { Component, EventEmitter, Input, Output } from '@angular/core';
import { ConversationSummary } from '../chat-api.service';

@Component({
  selector: 'app-history-panel',
  standalone: true,
  styleUrl: './history-panel.component.scss',
  templateUrl: './history-panel.component.html',
})
export class HistoryPanelComponent {
  @Input() conversations: ConversationSummary[] = [];
  @Input() activeConversationId: string | null = null;
  @Input() isLoading = true;
  @Input() error = '';
  @Input() isOpen = false;

  @Output() readonly conversationSelected = new EventEmitter<string>();
  @Output() readonly conversationDeleteRequested = new EventEmitter<string>();
  @Output() readonly retryRequested = new EventEmitter<void>();
}
