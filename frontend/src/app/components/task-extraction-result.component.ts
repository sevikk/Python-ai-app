import { Component, Input } from '@angular/core';
import { TaskExtractionResponse } from '../chat-api.service';

@Component({
  selector: 'app-task-extraction-result',
  standalone: true,
  styleUrl: './task-extraction-result.component.scss',
  templateUrl: './task-extraction-result.component.html',
})
export class TaskExtractionResultComponent {
  @Input() isLoading = false;
  @Input() error = '';
  @Input() result: TaskExtractionResponse | null = null;
}
