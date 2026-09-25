import { Component, computed, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import {
  MAT_DIALOG_DATA,
  MatDialogRef,
  MatDialogModule,
} from '@angular/material/dialog';
import { ApiService } from '../../../services/api.service';
import { Node } from '../../../models/api.models';

export const DIALOG_STATUS_IDLE = 'idle';
export const DIALOG_STATUS_SUCCESS = 'success';
export const DIALOG_STATUS_ERROR = 'error';

export type DialogSubmitStatus =
  | typeof DIALOG_STATUS_IDLE
  | typeof DIALOG_STATUS_SUCCESS
  | typeof DIALOG_STATUS_ERROR;

export const MAX_MESSAGE_LENGTH = 128;

export interface MessageDialogData {
  node: Node;
}

@Component({
  selector: 'app-message-dialog',
  standalone: true,
  imports: [CommonModule, FormsModule, MatDialogModule],
  templateUrl: './message-dialog.component.html',
  styleUrl: './message-dialog.component.scss',
})
export class MessageDialogComponent {
  readonly dialogRef = inject(MatDialogRef<MessageDialogComponent>);
  readonly data = inject<MessageDialogData>(MAT_DIALOG_DATA);
  private readonly api = inject(ApiService);

  readonly DIALOG_STATUS_IDLE = DIALOG_STATUS_IDLE;
  readonly DIALOG_STATUS_SUCCESS = DIALOG_STATUS_SUCCESS;
  readonly DIALOG_STATUS_ERROR = DIALOG_STATUS_ERROR;
  readonly MAX_MESSAGE_LENGTH = MAX_MESSAGE_LENGTH;

  readonly messageText = signal<string>('');
  readonly isSubmitting = signal<boolean>(false);
  readonly status = signal<DialogSubmitStatus>(DIALOG_STATUS_IDLE);
  readonly statusMessage = signal<string>('');

  readonly trimmedLength = computed(() => this.messageText().trim().length);
  readonly isLengthValid = computed(() => this.messageText().length <= MAX_MESSAGE_LENGTH);
  readonly isValid = computed(() => this.trimmedLength() > 0 && this.isLengthValid());

  onMessageInput(event: Event): void {
    const input = event.target as HTMLTextAreaElement;
    this.messageText.set(input.value);
    if (this.status() !== DIALOG_STATUS_IDLE) {
      this.status.set(DIALOG_STATUS_IDLE);
      this.statusMessage.set('');
    }
  }

  async send(): Promise<void> {
    if (!this.isValid() || this.isSubmitting()) {
      return;
    }

    this.isSubmitting.set(true);
    this.status.set(DIALOG_STATUS_IDLE);
    this.statusMessage.set('');

    try {
      const response = await this.api.postDisplay(
        this.data.node.device_id,
        this.messageText().trim()
      );

      if (response && response.status === 'success') {
        this.status.set(DIALOG_STATUS_SUCCESS);
        this.statusMessage.set(`Message successfully sent to ${this.data.node.device_id}.`);
        setTimeout(() => {
          this.dialogRef.close(true);
        }, 1200);
      } else {
        this.status.set(DIALOG_STATUS_ERROR);
        this.statusMessage.set(response?.error || 'Failed to send message to node.');
      }
    } catch (err: unknown) {
      this.status.set(DIALOG_STATUS_ERROR);
      const msg = err instanceof Error ? err.message : 'An unexpected error occurred.';
      this.statusMessage.set(msg);
    } finally {
      this.isSubmitting.set(false);
    }
  }

  close(): void {
    this.dialogRef.close(false);
  }
}
