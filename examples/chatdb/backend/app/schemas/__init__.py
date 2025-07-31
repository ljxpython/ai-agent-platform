# Import and re-export schema classes
from app.schemas.chat_history import (
    ChatHistoryListResponse,
    ChatHistoryResponse,
    ChatHistorySnapshot,
    ChatHistorySnapshotCreate,
    ChatMessage,
    ChatMessageCreate,
    ChatMessageUpdate,
    ChatSession,
    ChatSessionCreate,
    ChatSessionUpdate,
    RestoreChatHistoryResponse,
    SaveChatHistoryRequest,
)
from app.schemas.db_connection import (
    DBConnection,
    DBConnectionCreate,
    DBConnectionInDB,
    DBConnectionUpdate,
)
from app.schemas.query import QueryRequest, QueryResponse
from app.schemas.schema_column import (
    SchemaColumn,
    SchemaColumnCreate,
    SchemaColumnUpdate,
    SchemaColumnWithMappings,
)
from app.schemas.schema_relationship import (
    SchemaRelationship,
    SchemaRelationshipCreate,
    SchemaRelationshipDetailed,
    SchemaRelationshipUpdate,
)
from app.schemas.schema_table import (
    SchemaTable,
    SchemaTableCreate,
    SchemaTableUpdate,
    SchemaTableWithRelationships,
)
from app.schemas.value_mapping import (
    ValueMapping,
    ValueMappingCreate,
    ValueMappingUpdate,
)
