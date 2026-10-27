import { relations } from 'drizzle-orm';
import { integer, pgTable, serial, text, timestamp } from 'drizzle-orm/pg-core';

export const users = pgTable('users', {
  id: serial('id').primaryKey(),
  uid: text('uid').notNull().unique(),
  email: text('email').notNull(),
  createdAt: timestamp('created_at').defaultNow(),
});

export const workspaceIntegrations = pgTable('workspace_integrations', {
  id: serial('id').primaryKey(),
  userId: integer('user_id')
    .references(() => users.id)
    .notNull(),
  serviceName: text('service_name').notNull(),
  status: text('status').default('active'),
  createdAt: timestamp('created_at').defaultNow(),
});

export const voiceSessions = pgTable('voice_sessions', {
  id: serial('id').primaryKey(),
  userId: integer('user_id')
    .references(() => users.id)
    .notNull(),
  summary: text('summary').notNull(),
  transcriptCount: integer('transcript_count').default(0),
  createdAt: timestamp('created_at').defaultNow(),
});

export const usersRelations = relations(users, ({ many }) => ({
  workspaceIntegrations: many(workspaceIntegrations),
  voiceSessions: many(voiceSessions),
}));
