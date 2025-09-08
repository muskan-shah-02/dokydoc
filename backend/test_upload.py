#!/usr/bin/env python3
"""
Test script to manually create a document and trigger the multi-pass DAE processing
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db.session import SessionLocal
from app import crud, schemas
from app.services.analysis_service import dae

async def test_dae():
    """Test the Document Analysis Engine with a sample document"""
    
    # Create database session
    db = SessionLocal()
    
    try:
        # Read the test file content
        with open("uploads/test_document.txt", "r", encoding="utf-8") as f:
            content = f.read()
        
        # Create a test document directly in the database
        from app.models.document import Document
        
        document = Document(
            filename="test_document.txt",
            raw_text=content,
            status="uploaded",
            progress=0
        )
        
        db.add(document)
        db.commit()
        db.refresh(document)
        
        print(f"Created document with ID: {document.id}")
        print(f"Document raw text length: {len(content)}")
        
        # Run the multi-pass DAE
        print("Starting multi-pass DAE analysis...")
        success = await dae.analyze_document(db=db, document_id=document.id, learning_mode=True)
        
        if success:
            print("✅ Multi-pass DAE analysis completed successfully!")
            
            # Check the results
            updated_doc = crud.document.get(db=db, id=document.id)
            print(f"Document status: {updated_doc.status}")
            print(f"Document progress: {updated_doc.progress}")
            print(f"Composition analysis: {updated_doc.composition_analysis}")
            
            # Check segments
            segments = crud.document_segment.get_multi_by_document(db=db, document_id=document.id)
            print(f"Created {len(segments)} segments:")
            for segment in segments:
                print(f"  - {segment.segment_type}: chars {segment.start_char_index}-{segment.end_char_index}")
            
            # Check analysis results
            analysis_results = crud.analysis_result.get_multi_by_document(db=db, document_id=document.id)
            print(f"Created {len(analysis_results)} analysis results")
            
        else:
            print("❌ Multi-pass DAE analysis failed!")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(test_dae())
