/**
 * The signed-in user. Placeholder data until multi-user login exists; the login page will
 * replace this source, and the account components only read from it.
 */
export interface CurrentUser {
  name: string
  handle: string
  email: string
  /** Image reference; empty shows the name's first character. */
  avatar: string
  joinedAt: string
}

export const currentUser: Readonly<CurrentUser> = {
  name: '测试账号',
  handle: 'test',
  email: 'test@example.com',
  avatar: '',
  joinedAt: '2026-11-25',
}
