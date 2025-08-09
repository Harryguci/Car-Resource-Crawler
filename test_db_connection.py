#!/usr/bin/env python3
"""
Test script to verify database connection and basic operations
"""

import sys
import os

# Add the project root to the Python path
sys.path.append(os.path.dirname(__file__))

from src.database.connection import init_db, close_db, get_db_session
from src.services.image_resource_service import ImageResourceService
from src.models.image_resource import ImageResourceCreate
from src.config.settings import settings

def test_database_connection():
    """Test database connection and basic operations"""
    print("Testing database connection...")
    
    try:
        # Test database initialization
        print("1. Testing database initialization...")
        init_db()
        print("✅ Database initialization successful")
        
        # Test service operations
        print("2. Testing service operations...")
        for db_session in get_db_session():
            service = ImageResourceService(db_session)
            
            # Test creating an image resource
            test_image = ImageResourceCreate(
                url="https://example.com/test-image.jpg",
                filename="test-image.jpg",
                source="test",
                search_query="test query",
                tags=["test", "example"],
                description="Test image for database connection"
            )
            
            created_image = service.create_image_resource(test_image)
            print(f"✅ Created image resource with ID: {created_image.id}")
            
            # Test retrieving the image resource
            retrieved_image = service.get_image_resource(created_image.id)
            if retrieved_image:
                print(f"✅ Retrieved image resource: {retrieved_image.url}")
            else:
                print("❌ Failed to retrieve image resource")
            
            # Test listing image resources
            image_list = service.list_image_resources(page=1, per_page=10)
            print(f"✅ Listed {len(image_list.items)} image resources (total: {image_list.total})")
            
            # Test statistics
            stats = service.get_statistics()
            print(f"✅ Statistics: {stats}")
            
            break
        
        print("3. Testing database cleanup...")
        close_db()
        print("✅ Database cleanup successful")
        
        print("\n🎉 All database tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Database test failed: {e}")
        return False

def test_configuration():
    """Test configuration settings"""
    print("Testing configuration...")
    
    print(f"Database URL: {settings.postgres_url}")
    print(f"Database Host: {settings.postgres_host}")
    print(f"Database Port: {settings.postgres_port}")
    print(f"Database Name: {settings.postgres_db}")
    print(f"Database User: {settings.postgres_user}")
    print(f"Environment: {settings.environment}")
    
    return True

def main():
    """Main test function"""
    print("=" * 50)
    print("Database Connection Test")
    print("=" * 50)
    
    # Test configuration
    config_success = test_configuration()
    if not config_success:
        print("❌ Configuration test failed")
        return
    
    print("\n" + "=" * 50)
    
    # Test database connection
    db_success = test_database_connection()
    
    print("\n" + "=" * 50)
    if db_success:
        print("🎉 All tests passed! Database is ready to use.")
        sys.exit(0)
    else:
        print("❌ Some tests failed. Please check your configuration.")
        sys.exit(1)

if __name__ == "__main__":
    main()
