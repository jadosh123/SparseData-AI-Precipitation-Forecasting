## Summary: How to Move DB Data Between Computers

Since the live database folders are separate (one on Laptop, one on Desktop) to keep them fast, you use the Backup/Restore method to sync them.

- On Laptop: Run the "Dump" command (via Gemini). This creates a .sql file in your Google Drive folder.

- Google Drive: Syncs that .sql file to your Desktop automatically.

- On Desktop: You run the "Restore" command. This reads the file from Drive and updates your fast, local Linux database.

