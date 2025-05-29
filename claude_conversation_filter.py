#!/usr/bin/env python3
"""
Claude Conversation Filter Script

This script reads Claude exported conversation data, lists available users,
allows selection of a specific user, and exports only that user's conversations
to a new JSON file.

Supports both individual and Teams export formats:
- Individual format: uses 'user_id' and 'messages' fields
- Teams format: uses 'account' field with user uuid and 'chat_messages' field
"""

import json
import os
import sys
from collections import defaultdict
from datetime import datetime


def load_conversations(file_path):
    """Load conversations from JSON file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data
    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found.")
        return None
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON format in '{file_path}'.")
        return None
    except Exception as e:
        print(f"Error loading file: {e}")
        return None


def load_user_info(file_path):
    """Load user information from users.json file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Create a mapping of user_id -> user_info
        user_mapping = {}
        
        if isinstance(data, list):
            # Array format: [{"id": "uuid", "name": "...", "email": "..."}, ...]
            for user in data:
                if isinstance(user, dict):
                    user_id = user.get('id') or user.get('uuid') or user.get('user_id')
                    if user_id:
                        user_mapping[str(user_id)] = {
                            'name': user.get('name') or user.get('display_name') or user.get('full_name'),
                            'email': user.get('email') or user.get('email_address'),
                            'id': str(user_id)
                        }
        
        elif isinstance(data, dict):
            # Object format: {"uuid": {"name": "...", "email": "..."}, ...}
            for user_id, user_info in data.items():
                if isinstance(user_info, dict):
                    user_mapping[str(user_id)] = {
                        'name': user_info.get('name') or user_info.get('display_name') or user_info.get('full_name'),
                        'email': user_info.get('email') or user_info.get('email_address'),
                        'id': str(user_id)
                    }
        
        return user_mapping
    
    except FileNotFoundError:
        print(f"Note: User info file '{file_path}' not found. Will display user IDs only.")
        return {}
    except json.JSONDecodeError:
        print(f"Warning: Invalid JSON format in '{file_path}'. Will display user IDs only.")
        return {}
    except Exception as e:
        print(f"Warning: Error loading user info: {e}. Will display user IDs only.")
        return {}


def get_user_display_name(user_id, user_info_mapping):
    """Get a formatted display name for a user."""
    if not user_info_mapping or str(user_id) not in user_info_mapping:
        return str(user_id)
    
    user_info = user_info_mapping[str(user_id)]
    name = user_info.get('name')
    email = user_info.get('email')
    
    # Format: "Name (email@domain.com)"
    if name and email:
        return f"{name} ({email})"
    elif name:
        return f"{name} [{user_id[:8]}...]"
    elif email:
        return f"{email} [{user_id[:8]}...]"
    else:
        return str(user_id)


def extract_users(conversations_data):
    """Extract unique users from conversations data."""
    users = set()
    
    # Handle different possible data structures
    if isinstance(conversations_data, list):
        # If data is a list of conversations
        for conversation in conversations_data:
            if isinstance(conversation, dict):
                # Look for user identifier in various possible fields
                user_id = (conversation.get('user_id') or 
                          conversation.get('userId') or 
                          conversation.get('user') or
                          conversation.get('author'))
                
                # Teams format: check for account field with user uuid
                if not user_id and 'account' in conversation:
                    account = conversation['account']
                    if isinstance(account, dict):
                        user_id = account.get('uuid') or account.get('id')
                    elif isinstance(account, str):
                        user_id = account
                
                if user_id:
                    users.add(str(user_id))
                
                # Also check in messages if present (regular format)
                messages = conversation.get('messages', [])
                for message in messages:
                    if isinstance(message, dict):
                        msg_user = (message.get('user_id') or 
                                   message.get('userId') or 
                                   message.get('user') or
                                   message.get('author') or
                                   message.get('sender'))
                        if msg_user:
                            users.add(str(msg_user))
                
                # Teams format: check chat_messages
                chat_messages = conversation.get('chat_messages', [])
                for message in chat_messages:
                    if isinstance(message, dict):
                        msg_user = (message.get('user_id') or 
                                   message.get('userId') or 
                                   message.get('user') or
                                   message.get('author') or
                                   message.get('sender'))
                        if msg_user:
                            users.add(str(msg_user))
    
    elif isinstance(conversations_data, dict):
        # If data is a dict, it might have a conversations key or be keyed by user
        if 'conversations' in conversations_data:
            return extract_users(conversations_data['conversations'])
        else:
            # Data might be keyed by user ID
            users.update(conversations_data.keys())
    
    return sorted(list(users))


def get_user_conversation_count(conversations_data, user_id):
    """Count conversations for a specific user."""
    count = 0
    
    if isinstance(conversations_data, list):
        for conversation in conversations_data:
            if isinstance(conversation, dict):
                # Check if conversation belongs to user
                conv_user = (conversation.get('user_id') or 
                           conversation.get('userId') or 
                           conversation.get('user') or
                           conversation.get('author'))
                
                # Teams format: check account field
                if not conv_user and 'account' in conversation:
                    account = conversation['account']
                    if isinstance(account, dict):
                        conv_user = account.get('uuid') or account.get('id')
                    elif isinstance(account, str):
                        conv_user = account
                
                if str(conv_user) == str(user_id):
                    count += 1
                else:
                    # Check messages for user (regular format)
                    messages = conversation.get('messages', [])
                    for message in messages:
                        if isinstance(message, dict):
                            msg_user = (message.get('user_id') or 
                                       message.get('userId') or 
                                       message.get('user') or
                                       message.get('author') or
                                       message.get('sender'))
                            if str(msg_user) == str(user_id):
                                count += 1
                                break
                    
                    # Teams format: check chat_messages for user
                    if count == 0:  # Only check if not already found
                        chat_messages = conversation.get('chat_messages', [])
                        for message in chat_messages:
                            if isinstance(message, dict):
                                msg_user = (message.get('user_id') or 
                                           message.get('userId') or 
                                           message.get('user') or
                                           message.get('author') or
                                           message.get('sender'))
                                if str(msg_user) == str(user_id):
                                    count += 1
                                    break
    
    elif isinstance(conversations_data, dict):
        if 'conversations' in conversations_data:
            return get_user_conversation_count(conversations_data['conversations'], user_id)
        elif str(user_id) in conversations_data:
            # Data is keyed by user
            user_data = conversations_data[str(user_id)]
            if isinstance(user_data, list):
                count = len(user_data)
            elif isinstance(user_data, dict) and 'conversations' in user_data:
                count = len(user_data['conversations'])
    
    return count


def filter_conversations_by_user(conversations_data, selected_user):
    """Filter conversations for a specific user."""
    filtered_conversations = []
    
    if isinstance(conversations_data, list):
        for conversation in conversations_data:
            if isinstance(conversation, dict):
                # Check if conversation belongs to user
                conv_user = (conversation.get('user_id') or 
                           conversation.get('userId') or 
                           conversation.get('user') or
                           conversation.get('author'))
                
                # Teams format: check account field
                if not conv_user and 'account' in conversation:
                    account = conversation['account']
                    if isinstance(account, dict):
                        conv_user = account.get('uuid') or account.get('id')
                    elif isinstance(account, str):
                        conv_user = account
                
                if str(conv_user) == str(selected_user):
                    filtered_conversations.append(conversation)
                else:
                    # Check if any message in conversation belongs to user (regular format)
                    messages = conversation.get('messages', [])
                    user_messages = []
                    for message in messages:
                        if isinstance(message, dict):
                            msg_user = (message.get('user_id') or 
                                       message.get('userId') or 
                                       message.get('user') or
                                       message.get('author') or
                                       message.get('sender'))
                            if str(msg_user) == str(selected_user):
                                user_messages.append(message)
                    
                    if user_messages:
                        # Create a new conversation with only user's messages
                        filtered_conv = conversation.copy()
                        filtered_conv['messages'] = user_messages
                        filtered_conversations.append(filtered_conv)
                    else:
                        # Teams format: check chat_messages for user
                        chat_messages = conversation.get('chat_messages', [])
                        user_chat_messages = []
                        for message in chat_messages:
                            if isinstance(message, dict):
                                msg_user = (message.get('user_id') or 
                                           message.get('userId') or 
                                           message.get('user') or
                                           message.get('author') or
                                           message.get('sender'))
                                if str(msg_user) == str(selected_user):
                                    user_chat_messages.append(message)
                        
                        if user_chat_messages:
                            # Create a new conversation with only user's chat messages
                            filtered_conv = conversation.copy()
                            filtered_conv['chat_messages'] = user_chat_messages
                            # Remove regular messages field if it exists but was empty for this user
                            if 'messages' in filtered_conv and not user_messages:
                                filtered_conv.pop('messages', None)
                            filtered_conversations.append(filtered_conv)
    
    elif isinstance(conversations_data, dict):
        if 'conversations' in conversations_data:
            filtered_conversations = filter_conversations_by_user(
                conversations_data['conversations'], selected_user
            )
        elif str(selected_user) in conversations_data:
            # Data is keyed by user
            user_data = conversations_data[str(selected_user)]
            if isinstance(user_data, list):
                filtered_conversations = user_data
            elif isinstance(user_data, dict):
                filtered_conversations = [user_data]
    
    return filtered_conversations


def save_filtered_conversations(filtered_data, output_path, selected_user, user_info_mapping=None, include_header=True):
    """Save filtered conversations to a new JSON file."""
    try:
        if include_header:
            # Get user display info for metadata
            user_display = get_user_display_name(selected_user, user_info_mapping or {})
            
            output_data = {
                "user_id": selected_user,
                "user_display": user_display,
                "export_date": datetime.now().isoformat(),
                "conversation_count": len(filtered_data),
                "conversations": filtered_data
            }
        else:
            # Export only the conversations array without header metadata
            output_data = filtered_data
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        print(f"\nSuccess! Exported {len(filtered_data)} conversations to '{output_path}'")
        if not include_header:
            print("(Header metadata excluded)")
        return True
    except Exception as e:
        print(f"Error saving file: {e}")
        return False


def main():
    """Main function to run the conversation filter."""
    print("Claude Conversation Filter Script")
    print("=" * 40)
    
    # Get input file path
    input_file = input("Enter path to Claude conversations JSON file: ").strip()
    
    if not input_file:
        input_file = "conversations.json"  # Default filename
    
    # Load conversations
    print(f"\nLoading conversations from '{input_file}'...")
    conversations_data = load_conversations(input_file)
    
    if conversations_data is None:
        return
    
    # Try to load user information
    users_file = input("Enter path to users.json file (optional, press Enter to skip): ").strip()
    
    user_info_mapping = {}
    if users_file:
        print(f"Loading user information from '{users_file}'...")
        user_info_mapping = load_user_info(users_file)
    else:
        # Try to find users.json in the same directory as conversations file
        import os
        base_dir = os.path.dirname(input_file) if os.path.dirname(input_file) else "."
        default_users_file = os.path.join(base_dir, "users.json")
        
        if os.path.exists(default_users_file):
            print(f"Found users.json in same directory, loading user information...")
            user_info_mapping = load_user_info(default_users_file)
    
    # Extract users
    print("Extracting users...")
    users = extract_users(conversations_data)
    
    if not users:
        print("No users found in the conversation data.")
        return
    
    # Display available users
    print(f"\nFound {len(users)} user(s):")
    print("-" * 60)
    
    for i, user in enumerate(users, 1):
        count = get_user_conversation_count(conversations_data, user)
        display_name = get_user_display_name(user, user_info_mapping)
        print(f"{i}. {display_name}")
        print(f"   └── {count} conversations | ID: {user}")
        print()
    
    # User selection
    while True:
        try:
            selection = input(f"Select user (1-{len(users)}) or 'q' to quit: ").strip()
            
            if selection.lower() == 'q':
                print("Goodbye!")
                return
            
            user_index = int(selection) - 1
            if 0 <= user_index < len(users):
                selected_user = users[user_index]
                break
            else:
                print(f"Please enter a number between 1 and {len(users)}")
        
        except ValueError:
            print("Please enter a valid number or 'q' to quit")
    
    # Show selected user info
    selected_display = get_user_display_name(selected_user, user_info_mapping)
    print(f"\nSelected user: {selected_display}")
    
    # Filter conversations
    print(f"Filtering conversations...")
    filtered_conversations = filter_conversations_by_user(conversations_data, selected_user)
    
    if not filtered_conversations:
        print(f"No conversations found for selected user")
        return
    
    # Generate output filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Use display name for filename if available, otherwise use user ID
    if user_info_mapping and str(selected_user) in user_info_mapping:
        user_info = user_info_mapping[str(selected_user)]
        name = user_info.get('name', '').replace(' ', '_')
        if name:
            safe_name = "".join(c for c in name if c.isalnum() or c in "-_")
            output_file = f"claude_conversations_{safe_name}_{timestamp}.json"
        else:
            safe_user_id = "".join(c for c in selected_user if c.isalnum() or c in "-_")
            output_file = f"claude_conversations_{safe_user_id}_{timestamp}.json"
    else:
        safe_user_id = "".join(c for c in selected_user if c.isalnum() or c in "-_")
        output_file = f"claude_conversations_{safe_user_id}_{timestamp}.json"
    
    # Option to customize output filename
    custom_output = input(f"\nOutput filename (default: {output_file}): ").strip()
    if custom_output:
        output_file = custom_output
    
    # Ensure .json extension
    if not output_file.lower().endswith('.json'):
        output_file += '.json'
    
    # Ask about header inclusion
    while True:
        include_header_input = input("\nInclude header metadata (user info, export date, count)? (y/n, default: y): ").strip().lower()
        if include_header_input in ['', 'y', 'yes']:
            include_header = True
            break
        elif include_header_input in ['n', 'no']:
            include_header = False
            break
        else:
            print("Please enter 'y' for yes or 'n' for no")
    
    # Save filtered conversations
    success = save_filtered_conversations(filtered_conversations, output_file, selected_user, user_info_mapping, include_header)
    
    if success:
        print(f"File saved successfully!")
        print(f"User: {selected_display}")
        print(f"User ID: {selected_user}")
        print(f"Conversations: {len(filtered_conversations)}")
        print(f"Output file: {output_file}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user.")
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        sys.exit(1)